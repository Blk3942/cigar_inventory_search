from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterator

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.http_util import build_url, fetch_text

_DEFAULT_SEEDS: dict[str, list[str]] = {
    "tecon-gmbh": [
        "https://www.tecon-gmbh.de/index.php?cPath=2359",
        "https://www.tecon-gmbh.de/index.php?cPath=2359_1799",
        "https://www.tecon-gmbh.de/index.php?cPath=2359_1137",
    ],
}


def _parse_price_from_product_html(html: str) -> tuple[str, bool]:
    m = re.search(
        r'property="product:price:amount"\s+content="([\d.]+)"',
        html,
        re.I,
    )
    if m:
        try:
            return format(Decimal(m.group(1)).quantize(Decimal("0.01")), "f"), True
        except Exception:
            pass
    m = re.search(r'class="[^"]*productPrice[^"]*"[^>]*>\s*([^<]+)', html, re.I)
    if m:
        txt = m.group(1)
        num = re.search(r"([\d]{1,6}[.,]\d{2})", txt.replace("\xa0", " "))
        if num:
            raw = num.group(1).replace(".", "").replace(",", ".")
            try:
                return format(Decimal(raw).quantize(Decimal("0.01")), "f"), True
            except Exception:
                pass
    m = re.search(r'itemprop="price"[^>]*content="([\d.,]+)"', html, re.I)
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return format(Decimal(raw).quantize(Decimal("0.01")), "f"), True
        except Exception:
            pass
    return "0", True


def _listing_product_ids(html: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in re.finditer(
        r'product_info\.php\?products_id=(\d+)',
        html,
        re.I,
    ):
        pid = m.group(1)
        out.append((pid, f"p{pid}"))
    seen: set[str] = set()
    uniq: list[tuple[str, str]] = []
    for pid, h in out:
        if pid not in seen:
            seen.add(pid)
            uniq.append((pid, h))
    return uniq


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    seeds = site.adapter_options.get("seed_urls")
    if isinstance(seeds, str):
        seeds = [seeds]
    if not seeds:
        seeds = _DEFAULT_SEEDS.get(site.id, [])
    if not seeds:
        return
    base = site.base_url.rstrip("/")
    max_pages = site.max_pages if site.max_pages is not None else 5
    max_products = int(site.adapter_options.get("max_scrape_products") or 200)
    seen_pid: set[str] = set()
    collected = 0
    for seed in seeds:
        if collected >= max_products:
            break
        for page in range(1, max_pages + 1):
            if collected >= max_products:
                break
            url = seed
            if page > 1:
                sep = "&" if "?" in seed else "?"
                url = f"{seed}{sep}page={page}"
            try:
                html = fetch_text(url, timeout=45.0)
            except Exception:
                break
            pairs = _listing_product_ids(html)
            if page > 1 and not pairs:
                break
            for pid, _ in pairs:
                if collected >= max_products:
                    break
                if pid in seen_pid:
                    continue
                seen_pid.add(pid)
                purl = build_url(base, "/product_info.php", {"products_id": pid})
                try:
                    phtml = fetch_text(purl, timeout=35.0)
                except Exception:
                    continue
                title_m = re.search(r"<title>([^<|]+)", phtml, re.I)
                title = (
                    title_m.group(1).strip()
                    if title_m
                    else f"Product {pid}"
                )
                price_s, available = _parse_price_from_product_html(phtml)
                variant = {
                    "id": None,
                    "title": "Default Title",
                    "option1": "默认",
                    "option2": None,
                    "option3": None,
                    "sku": pid,
                    "price": price_s,
                    "available": available,
                    "inventory_quantity": None,
                }
                collected += 1
                yield {
                    "title": title,
                    "handle": f"oscommerce-{pid}",
                    "body_html": "",
                    "vendor": "",
                    "product_type": "Cigars",
                    "tags": ["cigar"],
                    "__cigar_section__": True,
                    "variants": [variant],
                    "__product_url__": purl,
                }

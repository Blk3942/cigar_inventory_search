from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.http_util import fetch_text

_DEFAULT_SEEDS: dict[str, list[str]] = {
    "tabak-traeber": [
        "https://www.tabak-traeber.de/Zigarren:::1.html",
    ],
}


def _parse_price(html: str) -> tuple[str, bool]:
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
    m = re.search(
        r'itemprop="price"[^>]*content="([\d.,]+)"',
        html,
        re.I,
    )
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return format(Decimal(raw).quantize(Decimal("0.01")), "f"), True
        except Exception:
            pass
    m = re.search(r'class="[^"]*price[^"]*"[^>]*>[\s\S]{0,200}?([\d]{1,6}[.,]\d{2})', html, re.I)
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return format(Decimal(raw).quantize(Decimal("0.01")), "f"), True
        except Exception:
            pass
    return "0", True


def _product_links(listing_html: str, base: str) -> list[str]:
    links: list[str] = []
    for m in re.finditer(r'href="(https?://[^"]+\.html)"', listing_html):
        u = m.group(1)
        if "tabak-traeber.de" in u and ":::" in u and "/Zigarren" in u:
            links.append(u)
    for m in re.finditer(r'href="(/[^"]+\.html)"', listing_html):
        u = urljoin(base + "/", m.group(1))
        if ":::" in u and "Zigarren" in u:
            links.append(u)
    seen: set[str] = set()
    out: list[str] = []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    seeds = site.adapter_options.get("seed_urls")
    if isinstance(seeds, str):
        seeds = [seeds]
    if not seeds:
        seeds = _DEFAULT_SEEDS.get(site.id, [])
    if not seeds:
        return
    base = site.base_url.rstrip("/")
    max_list_pages = site.max_pages if site.max_pages is not None else 8
    max_products = int(site.adapter_options.get("max_scrape_products") or 250)
    collected = 0
    seen_urls: set[str] = set()
    for seed in seeds:
        if collected >= max_products:
            break
        for page in range(1, max_list_pages + 1):
            if collected >= max_products:
                break
            url = seed
            if page > 1:
                sep = "&" if "?" in seed else "?"
                if "?" in seed:
                    url = f"{seed}{sep}page={page}"
                else:
                    url = f"{seed}{sep}page={page}"
            try:
                listing = fetch_text(url, timeout=45.0)
            except Exception:
                break
            links = _product_links(listing, base)
            if page > 1 and not links:
                break
            for plink in links:
                if collected >= max_products:
                    break
                if plink in seen_urls:
                    continue
                seen_urls.add(plink)
                try:
                    phtml = fetch_text(plink, timeout=35.0)
                except Exception:
                    continue
                title_m = re.search(r"<title>([^<|]+)", phtml, re.I)
                title = title_m.group(1).strip() if title_m else plink
                handle = urlparse(plink).path.strip("/").replace("/", "-")[:100]
                price_s, available = _parse_price(phtml)
                variant = {
                    "id": None,
                    "title": "Default Title",
                    "option1": "默认",
                    "option2": None,
                    "option3": None,
                    "sku": "",
                    "price": price_s,
                    "available": available,
                    "inventory_quantity": None,
                }
                collected += 1
                yield {
                    "title": title,
                    "handle": handle or "item",
                    "body_html": "",
                    "vendor": "",
                    "product_type": "Cigars",
                    "tags": ["cigar"],
                    "__cigar_section__": True,
                    "variants": [variant],
                    "__product_url__": plink,
                }

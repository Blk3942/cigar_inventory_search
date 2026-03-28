from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterator
from urllib.parse import urljoin

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.http_util import fetch_text

from cigar_inventory.adapters.scrape_util import extract_json_ld_products, price_from_ld_product


def _parse_price(html: str) -> tuple[str, bool]:
    for ld in extract_json_ld_products(html):
        got = price_from_ld_product(ld)
        if got:
            return got
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
    m = re.search(r'€\s*([\d]{1,6}[.,]\d{2})', html)
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return format(Decimal(raw).quantize(Decimal("0.01")), "f"), True
        except Exception:
            pass
    return "0", True


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    base = site.base_url.rstrip("/")
    start = str(
        site.adapter_options.get("start_url") or f"{base}/"
    )
    max_products = int(site.adapter_options.get("max_scrape_products") or 180)
    try:
        html = fetch_text(start, timeout=45.0)
    except Exception:
        return
    paths = set(
        re.findall(r'href="(/shop/[^"#?]+-p\d+)"', html, re.I)
    )
    paths |= set(
        re.findall(r'href="(https?://[^"#?]+/shop/[^"#?]+-p\d+)"', html, re.I)
    )
    seen: set[str] = set()
    n = 0
    for path in paths:
        if n >= max_products:
            break
        url = urljoin(base + "/", path)
        if url in seen:
            continue
        seen.add(url)
        try:
            phtml = fetch_text(url, timeout=35.0)
        except Exception:
            continue
        title_m = re.search(r"<title>([^<|]+)", phtml, re.I)
        title = title_m.group(1).strip() if title_m else url
        handle = path.strip("/").replace("/", "-")[:120]
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
        n += 1
        yield {
            "title": title,
            "handle": handle,
            "body_html": "",
            "vendor": "",
            "product_type": "Shop",
            "tags": ["cigar"],
            "__cigar_section__": True,
            "variants": [variant],
            "__product_url__": url,
        }

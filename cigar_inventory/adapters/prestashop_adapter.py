from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Iterator
from urllib.parse import urlparse

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.http_util import fetch_text

from cigar_inventory.adapters.scrape_util import extract_json_ld_products, parse_sitemap_locs, price_from_ld_product


def _is_product_url(loc: str, base_netloc: str) -> bool:
    try:
        u = urlparse(loc)
    except Exception:
        return False
    if u.netloc != base_netloc:
        return False
    path = (u.path or "").lower()
    if path.endswith("/"):
        path = path[:-1]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return False
    # 排除纯分类页：常见为 /en/category 两段；商品多为多段且含数字段
    if re.search(r"-\d+\.html$", path) or re.search(r"/\d+-[\w-]+\.html$", path):
        return True
    if re.search(r"/\d+[\w-]*\.html$", path):
        return True
    return len(parts) >= 3 and path.endswith(".html")


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    base = site.base_url.rstrip("/")
    netloc = urlparse(base).netloc
    max_items = int(site.adapter_options.get("max_scrape_products") or 280)
    sm_url = str(site.adapter_options.get("sitemap_url") or f"{base}/sitemap.xml")
    try:
        xml = fetch_text(sm_url, timeout=60.0)
    except Exception:
        return
    locs = parse_sitemap_locs(xml)
    if not locs and "<sitemapindex" in xml.lower():
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc_el in root.findall(".//sm:loc", ns):
            if loc_el.text and "product" in loc_el.text.lower():
                try:
                    sub = fetch_text(loc_el.text.strip(), timeout=60.0)
                    locs.extend(parse_sitemap_locs(sub))
                except Exception:
                    continue
    seen: set[str] = set()
    n = 0
    for loc in locs:
        if n >= max_items:
            break
        if not _is_product_url(loc, netloc):
            continue
        if loc in seen:
            continue
        seen.add(loc)
        try:
            html = fetch_text(loc, timeout=35.0)
        except Exception:
            continue
        title_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        title = title_m.group(1).strip() if title_m else loc.rsplit("/", 1)[-1]
        handle = re.sub(r"[^\w\-]+", "-", urlparse(loc).path.strip("/").replace("/", "-"))[
            :120
        ] or "item"
        price_s = "0"
        available = True
        for ld in extract_json_ld_products(html):
            got = price_from_ld_product(ld)
            if got:
                price_s, available = got
                break
        if price_s == "0":
            pm = re.search(
                r'property="product:price:amount"\s+content="([\d.]+)"',
                html,
                re.I,
            )
            if pm:
                price_s = pm.group(1)
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
            "product_type": "PrestaShop",
            "tags": ["cigar"],
            "__cigar_section__": True,
            "variants": [variant],
            "__product_url__": loc,
        }

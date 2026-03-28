from __future__ import annotations

import urllib.parse
from typing import Any, Iterator

from cigar_inventory.http_util import get_json

PRODUCTS_PATH = "/products.json"
PAGE_SIZE = 250
DEFAULT_SHOPIFY_BASE = "https://cigarviu.com"


def iter_products(
    base_url: str = DEFAULT_SHOPIFY_BASE,
    page_size: int = PAGE_SIZE,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    page = 1
    base = base_url.rstrip("/")
    while True:
        if max_pages is not None and page > max_pages:
            break
        q = urllib.parse.urlencode({"limit": page_size, "page": page})
        url = f"{base}{PRODUCTS_PATH}?{q}"
        data = get_json(url)
        products = data.get("products") or []
        for p in products:
            yield p
        if len(products) < page_size:
            break
        page += 1


def product_url(handle: str, base_url: str = DEFAULT_SHOPIFY_BASE) -> str:
    return f"{base_url.rstrip('/')}/products/{handle}"


def variant_label(v: dict[str, Any]) -> str:
    opts = [v.get("option1"), v.get("option2"), v.get("option3")]
    return " / ".join(o for o in opts if o and o != "Default Title") or "默认"


def is_cigar_related(p: dict[str, Any]) -> bool:
    if p.get("__cigar_section__") is True:
        return True
    pt = (p.get("product_type") or "").lower()
    if "cigar" in pt or "zigar" in pt or "habanos" in pt:
        return True
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    blob = " ".join(tags).lower()
    if "cigar" in blob or "zigar" in blob or "habanos" in blob:
        return True
    return False


def variant_quantity_display(v: dict[str, Any], available: bool) -> str:
    q = v.get("inventory_quantity")
    if q is not None:
        try:
            return str(int(q))
        except (TypeError, ValueError):
            return str(q)
    if available:
        return "未公开"
    return "0"

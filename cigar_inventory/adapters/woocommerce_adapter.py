from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterator

from cigar_inventory.config_loader import SiteConfig
from cigar_inventory.http_util import build_url, get_json_any


def _wc_price_to_string(prices: dict[str, Any]) -> str:
    raw = str(prices.get("price") or "0")
    minor = int(prices.get("currency_minor_unit") or 2)
    if raw.replace(".", "").replace("-", "").isdigit() and "." not in raw and minor > 0:
        try:
            v = Decimal(raw) / (Decimal(10) ** minor)
            return format(v.quantize(Decimal("0.01")), "f")
        except Exception:
            pass
    raw = raw.replace(",", ".")
    try:
        return format(Decimal(raw).quantize(Decimal("0.01")), "f")
    except Exception:
        return "0"


def _map_wc_product(raw: dict[str, Any]) -> dict[str, Any]:
    prices = raw.get("prices") or {}
    tags = [t.get("slug") or t.get("name") or "" for t in (raw.get("tags") or [])]
    cats = raw.get("categories") or []
    cat_names = [c.get("name") or "" for c in cats]
    product_type = cat_names[0] if cat_names else "WooCommerce"
    vendor = ""
    for a in raw.get("attributes") or []:
        if (a.get("taxonomy") or "").startswith("pa_"):
            terms = a.get("terms") or []
            if terms:
                vendor = str(terms[0].get("name") or "")
                break
    available = bool(raw.get("is_in_stock")) and bool(raw.get("is_purchasable", True))
    price_s = _wc_price_to_string(prices)
    opt1 = "默认"
    attrs = raw.get("attributes") or []
    if attrs and raw.get("has_options"):
        parts = []
        for a in attrs[:3]:
            terms = a.get("terms") or []
            if len(terms) == 1:
                parts.append(str(terms[0].get("name") or ""))
        if parts:
            opt1 = " / ".join(parts)
    variant = {
        "id": raw.get("id"),
        "title": "Default Title",
        "option1": opt1,
        "option2": None,
        "option3": None,
        "sku": str(raw.get("sku") or ""),
        "price": price_s,
        "available": available,
        "inventory_quantity": None,
    }
    return {
        "title": str(raw.get("name") or ""),
        "handle": str(raw.get("slug") or str(raw.get("id") or "item")),
        "body_html": "",
        "vendor": vendor,
        "product_type": product_type,
        "tags": tags + [c.lower().replace(" ", "-") for c in cat_names if c],
        "variants": [variant],
    }


def iter_products(site: SiteConfig) -> Iterator[dict[str, Any]]:
    base = site.base_url.rstrip("/")
    ns = str(site.adapter_options.get("wc_store_namespace") or "wc/store/v1")
    per_page = int(site.adapter_options.get("wc_per_page") or 100)
    page = 1
    max_pages = site.max_pages
    while True:
        if max_pages is not None and page > max_pages:
            break
        url = build_url(
            base,
            f"/wp-json/{ns}/products",
            {"per_page": str(per_page), "page": str(page)},
        )
        chunk = get_json_any(url, timeout=60.0)
        if not isinstance(chunk, list) or not chunk:
            break
        for raw in chunk:
            if isinstance(raw, dict):
                yield _map_wc_product(raw)
        if len(chunk) < per_page:
            break
        page += 1

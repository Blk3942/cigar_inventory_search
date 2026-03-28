from __future__ import annotations

from decimal import Decimal
from typing import Any

from cigar_inventory.config_loader import FilterConfig


def _tags_blob(tags: Any) -> str:
    if not tags:
        return ""
    if isinstance(tags, str):
        return tags
    if not isinstance(tags, list):
        return str(tags)
    parts: list[str] = []
    for t in tags:
        if isinstance(t, str):
            parts.append(t)
        elif isinstance(t, dict):
            parts.append(str(t.get("name") or t.get("slug") or ""))
    return " ".join(parts)


def _text_blob(product: dict[str, Any]) -> str:
    parts = [
        product.get("title") or "",
        product.get("vendor") or "",
        _tags_blob(product.get("tags")),
        product.get("handle") or "",
    ]
    return " ".join(parts).lower()


def matches_brands(product: dict[str, Any], brands: list[str]) -> bool:
    if not brands:
        return True
    blob = _text_blob(product)
    return any(b.lower() in blob for b in brands)


def matches_product_keywords(product: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return True
    title = (product.get("title") or "").lower()
    return any(k.lower() in title for k in keywords)


def matches_handles(product: dict[str, Any], handles: list[str]) -> bool:
    if not handles:
        return True
    h = product.get("handle") or ""
    want = {x.strip().lower() for x in handles if x.strip()}
    return h.lower() in want


def matches_price_cny(pre_tax_cny: Decimal, flt: FilterConfig) -> bool:
    if flt.price_cny_pre_tax_min is not None and pre_tax_cny < flt.price_cny_pre_tax_min:
        return False
    if flt.price_cny_pre_tax_max is not None and pre_tax_cny > flt.price_cny_pre_tax_max:
        return False
    return True

from __future__ import annotations

from typing import Any


def resolve_brand(
    product: dict[str, Any],
    filter_brands: list[str],
    brand_hints: list[str],
) -> str:
    """
    优先从「筛选品牌 + brand_hints」里按最长匹配命中 title/tags；
    否则用首个 tag，再否则 vendor。
    """
    title = product.get("title") or ""
    tags = product.get("tags") or []
    blob = (title + " " + " ".join(tags)).lower()

    candidates = list(filter_brands) + list(brand_hints)
    candidates = sorted({b.strip() for b in candidates if b.strip()}, key=len, reverse=True)
    for b in candidates:
        if b.lower() in blob:
            return b
    if tags:
        return str(tags[0])
    v = product.get("vendor")
    if v:
        return str(v)
    return "—"

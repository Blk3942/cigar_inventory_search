from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any


def extract_json_ld_products(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        objs = data if isinstance(data, list) else [data]
        for o in objs:
            if isinstance(o, dict) and "@graph" in o:
                for x in o["@graph"]:
                    if isinstance(x, dict):
                        out.append(x)
            elif isinstance(o, dict):
                out.append(o)
    return out


def price_from_ld_product(o: dict[str, Any]) -> tuple[str, bool] | None:
    if not isinstance(o, dict):
        return None
    offers = o.get("offers")
    if offers is None:
        return None
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return None
    price = offers.get("price") or offers.get("lowPrice")
    if price is None:
        return None
    try:
        ps = format(Decimal(str(price)).quantize(Decimal("0.01")), "f")
    except Exception:
        return None
    avail = str(offers.get("availability") or "")
    available = "OutOfStock" not in avail and "SoldOut" not in avail
    return ps, available


def parse_sitemap_locs(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml, re.I)

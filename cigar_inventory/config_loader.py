from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass
class SiteConfig:
    id: str
    display_name: str
    base_url: str
    adapter: str
    currency: str
    only_cigar_related: bool = True
    max_pages: int | None = None
    enabled: bool = True
    adapter_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class FilterConfig:
    brands: list[str] = field(default_factory=list)
    product_keywords: list[str] = field(default_factory=list)
    product_handles: list[str] = field(default_factory=list)
    price_cny_pre_tax_min: Decimal | None = None
    price_cny_pre_tax_max: Decimal | None = None


@dataclass
class AppConfig:
    sites: list[SiteConfig]
    filters: FilterConfig
    tariff_rate: Decimal
    include_unavailable: bool
    brand_hints: list[str]

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> AppConfig:
        sites_in = raw.get("sites") or []
        sites: list[SiteConfig] = []
        for s in sites_in:
            sites.append(
                SiteConfig(
                    id=str(s.get("id") or s.get("base_url") or "site"),
                    display_name=str(s.get("display_name") or s.get("name") or s["base_url"]),
                    base_url=str(s["base_url"]).rstrip("/"),
                    adapter=str(s.get("adapter") or "shopify").lower(),
                    currency=str(s.get("currency") or "USD").upper(),
                    only_cigar_related=bool(s.get("only_cigar_related", True)),
                    max_pages=s.get("max_pages"),
                    enabled=bool(s.get("enabled", True)),
                    adapter_options=dict(s.get("adapter_options") or {}),
                )
            )

        f = raw.get("filters") or {}
        pcmin = f.get("price_cny_pre_tax_min")
        pcmax = f.get("price_cny_pre_tax_max")
        filters = FilterConfig(
            brands=[str(x) for x in (f.get("brands") or [])],
            product_keywords=[str(x) for x in (f.get("product_keywords") or [])],
            product_handles=[str(x) for x in (f.get("product_handles") or [])],
            price_cny_pre_tax_min=Decimal(str(pcmin)) if pcmin is not None else None,
            price_cny_pre_tax_max=Decimal(str(pcmax)) if pcmax is not None else None,
        )

        tr = raw.get("tariff_rate")
        tariff = Decimal(str(tr)) if tr is not None else Decimal("0.5")

        hints = [str(x) for x in (raw.get("brand_hints") or [])]

        return AppConfig(
            sites=sites,
            filters=filters,
            tariff_rate=tariff,
            include_unavailable=bool(raw.get("include_unavailable", False)),
            brand_hints=hints,
        )


def load_config(path: Path) -> AppConfig:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    return AppConfig.from_dict(data)

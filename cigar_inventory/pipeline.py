from __future__ import annotations

import csv
import json
import sys
import urllib.error
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from cigar_inventory.adapters import iter_normalized_products
from cigar_inventory.branding import resolve_brand
from cigar_inventory.config_loader import AppConfig, SiteConfig
from cigar_inventory.filters import (
    matches_brands,
    matches_handles,
    matches_price_cny,
    matches_product_keywords,
)
from cigar_inventory.fx import fetch_rate_to_cny
from cigar_inventory.stick_count import extract_cigar_stick_count
from cigar_inventory.shopify import is_cigar_related, product_url, variant_label


@dataclass
class ExportRow:
    网站: str
    品牌: str
    产品名称: str
    规格: str
    原价货币: str
    原价金额: str
    人民币税前: str
    人民币税后: str
    解析雪茄支数: str
    单支人民币税后: str
    链接: str


def _parse_price(s: str) -> Decimal:
    return Decimal(str(s).strip() or "0")


def _money_str(d: Decimal) -> str:
    q = d.quantize(Decimal("0.01"))
    return format(q, "f")


def _load_fx_rates(currencies: set[str]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for cur in currencies:
        c = cur.upper()
        if c in out:
            continue
        rate, _, _ = fetch_rate_to_cny(c)
        out[c] = rate
    return out


def _product_page_url(p: dict[str, Any], handle: str, site: SiteConfig) -> str:
    u = p.get("__product_url__")
    if isinstance(u, str) and u.startswith("http"):
        return u
    return product_url(handle, site.base_url)


def _append_rows_for_product(
    site: SiteConfig,
    cfg: AppConfig,
    p: dict[str, Any],
    fx_rates: dict[str, Decimal],
    rows: list[ExportRow],
) -> None:
    flt = cfg.filters
    if site.only_cigar_related and not is_cigar_related(p):
        return
    if not matches_brands(p, flt.brands):
        return
    if not matches_product_keywords(p, flt.product_keywords):
        return
    if not matches_handles(p, flt.product_handles):
        return

    handle = str(p.get("handle") or "")
    title = str(p.get("title") or "")
    url = _product_page_url(p, handle, site)
    brand = resolve_brand(p, flt.brands, cfg.brand_hints)

    cur = site.currency.upper()
    rate = fx_rates[cur]

    for v in p.get("variants") or []:
        if not isinstance(v, dict):
            continue
        available = bool(v.get("available"))
        if not cfg.include_unavailable and not available:
            continue

        price_orig = _parse_price(str(v.get("price") or "0"))
        if cur == "CNY":
            pre_cny = price_orig
        else:
            pre_cny = (price_orig * rate).quantize(Decimal("0.01"))

        if not matches_price_cny(pre_cny, flt):
            continue

        after = (pre_cny * (Decimal("1") + cfg.tariff_rate)).quantize(Decimal("0.01"))
        spec_str = variant_label(v)
        sticks = extract_cigar_stick_count(spec_str, title, handle)
        if sticks is not None and sticks > 0:
            dc = Decimal(sticks)
            after_each = (after / dc).quantize(Decimal("0.01"))
            sticks_s = str(sticks)
            after_each_s = _money_str(after_each)
        else:
            sticks_s = ""
            after_each_s = ""

        rows.append(
            ExportRow(
                网站=site.display_name,
                品牌=brand,
                产品名称=title,
                规格=spec_str,
                原价货币=cur,
                原价金额=_money_str(price_orig),
                人民币税前=_money_str(pre_cny),
                人民币税后=_money_str(after),
                解析雪茄支数=sticks_s,
                单支人民币税后=after_each_s,
                链接=url,
            )
        )


def collect_rows(cfg: AppConfig) -> list[ExportRow]:
    rows: list[ExportRow] = []
    enabled = [s for s in cfg.sites if s.enabled]
    currencies = {s.currency.upper() for s in enabled}
    fx_rates = _load_fx_rates(currencies) if currencies else {}

    for site in enabled:
        try:
            for p in iter_normalized_products(site):
                if isinstance(p, dict):
                    _append_rows_for_product(site, cfg, p, fx_rates, rows)
        except ValueError as e:
            print(
                f"[跳过] {site.display_name} ({site.id}): {e}",
                file=sys.stderr,
            )
        except urllib.error.HTTPError as e:
            print(
                f"[跳过] {site.display_name} ({site.id}): HTTP {e.code} {e.reason}",
                file=sys.stderr,
            )
        except urllib.error.URLError as e:
            print(
                f"[跳过] {site.display_name} ({site.id}): 网络错误 {e.reason!r}",
                file=sys.stderr,
            )
        except json.JSONDecodeError as e:
            print(
                f"[跳过] {site.display_name} ({site.id}): JSON 解析失败 ({e})",
                file=sys.stderr,
            )

    return rows


CSV_FIELDS = list(ExportRow.__dataclass_fields__.keys())


def write_csv(path: Path, rows: list[ExportRow]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def print_csv(rows: list[ExportRow]) -> None:
    w = csv.DictWriter(sys.stdout, fieldnames=CSV_FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow(asdict(r))


def write_json(path: Path, rows: list[ExportRow]) -> None:
    data = [asdict(r) for r in rows]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(rows: list[ExportRow]) -> None:
    print(json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2))

from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode

from cigar_inventory.http_util import get_json

FRANKFURTER_LATEST = "https://api.frankfurter.app/latest"


def fetch_rate_to_cny(from_currency: str) -> tuple[Decimal, str, dict[str, Any]]:
    """
    返回 (1 单位 from_currency 折合多少 CNY, 汇率日期, 原始 JSON)。
    数据源：Frankfurter（欧洲央行参考汇率，每次运行实时请求）。
    """
    cur = from_currency.strip().upper()
    if cur == "CNY":
        return Decimal("1"), "", {}

    qs = urlencode({"from": cur, "to": "CNY"})
    url = f"{FRANKFURTER_LATEST}?{qs}"
    data = get_json(url, timeout=30.0)
    date = str(data.get("date") or "")
    rates = data.get("rates") or {}
    if "CNY" not in rates:
        raise ValueError(f"汇率响应中缺少 CNY: {cur} -> {data}")
    rate = Decimal(str(rates["CNY"]))
    return rate, date, data


def format_fx_note(from_currency: str, rate: Decimal, fx_date: str) -> str:
    cur = from_currency.upper()
    if cur == "CNY":
        return "基准货币为 CNY"
    d = f" ({fx_date})" if fx_date else ""
    return f"1 {cur} = {rate} CNY{d}"

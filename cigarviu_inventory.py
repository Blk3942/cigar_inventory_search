#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 https://cigarviu.com/（Shopify）拉取商品与可售状态。

说明：
- Shopify 店铺公开的 /products.json 可分页获取目录；无需登录。
- 变体字段里的 available 表示当前是否可下单，不是仓库精确支数；
  多数店铺不会在公开接口里返回 inventory_quantity。

多站点、汇率与税后人民币请使用 run_inventory.py + config.json。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
from typing import Any

from cigar_inventory.shopify import (
    DEFAULT_SHOPIFY_BASE,
    is_cigar_related,
    iter_products,
    product_url,
    variant_label,
)

BASE = DEFAULT_SHOPIFY_BASE


def matches_query(p: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    q = query.lower()
    blob = " ".join(
        [
            p.get("title") or "",
            p.get("vendor") or "",
            p.get("product_type") or "",
            " ".join(p.get("tags") or []),
            p.get("handle") or "",
        ]
    ).lower()
    return q in blob


def summarize_variant(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant_id": v.get("id"),
        "label": variant_label(v),
        "sku": v.get("sku") or "",
        "price": v.get("price") or "",
        "compare_at_price": v.get("compare_at_price") or "",
        "available": bool(v.get("available")),
    }


def run_list_types() -> None:
    from collections import Counter

    c: Counter[str] = Counter()
    for p in iter_products(BASE):
        key = p.get("product_type") or "(空)"
        c[key] += 1
    for name, n in c.most_common():
        print(f"{n}\t{name}")


def run_fetch(args: argparse.Namespace) -> None:
    rows: list[dict[str, Any]] = []
    for p in iter_products(BASE, max_pages=args.max_pages):
        if not args.all_products and not is_cigar_related(p):
            continue
        if not matches_query(p, args.query):
            continue
        handle = p.get("handle") or ""
        title = p.get("title") or ""
        vendor = p.get("vendor") or ""
        ptype = p.get("product_type") or ""
        url = product_url(handle, BASE)
        for v in p.get("variants") or []:
            s = summarize_variant(v)
            if not args.include_unavailable and not s["available"]:
                continue
            rows.append(
                {
                    "title": title,
                    "product_type": ptype,
                    "vendor": vendor,
                    "variant": s["label"],
                    "sku": s["sku"],
                    "price": s["price"],
                    "compare_at_price": s["compare_at_price"],
                    "available": s["available"],
                    "url": url,
                    "variant_id": s["variant_id"],
                }
            )

    out_path: str | None = getattr(args, "output", None) or None
    csv_fields = [
        "title",
        "product_type",
        "vendor",
        "variant",
        "sku",
        "price",
        "compare_at_price",
        "available",
        "url",
        "variant_id",
    ]

    if args.format == "json":
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
                f.write("\n")
        else:
            json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
            print()
        print(f"共 {len(rows)} 条变体记录。", file=sys.stderr)
        return

    if args.format == "csv":
        if out_path:
            with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=csv_fields)
                w.writeheader()
                w.writerows(rows)
        else:
            w = csv.DictWriter(sys.stdout, fieldnames=csv_fields)
            w.writeheader()
            w.writerows(rows)
        print(f"共 {len(rows)} 条变体记录。", file=sys.stderr)
        return

    lines: list[str] = []
    for r in rows:
        status = "有货" if r["available"] else "无货"
        lines.append(
            f"[{status}] {r['price']} CHF\t{r['title']}"
            f"\n  规格: {r['variant']}\tSKU: {r['sku']}\t类型: {r['product_type']}"
            f"\n  {r['url']}\n"
        )
    text_out = "".join(lines)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text_out)
    else:
        print(text_out, end="")
    print(f"共 {len(rows)} 条变体记录。", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="检索 cigarviu.com 商品可售情况（Shopify products.json）。"
    )
    sub = p.add_subparsers(dest="command", required=True)

    s_fetch = sub.add_parser("fetch", help="拉取并筛选输出")
    s_fetch.add_argument(
        "-q",
        "--query",
        default="",
        help="在标题/厂商/类型/标签/handle 中子串搜索（不区分大小写）",
    )
    s_fetch.add_argument(
        "--all-products",
        action="store_true",
        help="不过滤，包含非雪茄类（配件、酒等）",
    )
    s_fetch.add_argument(
        "--include-unavailable",
        action="store_true",
        help="同时列出不可购买的变体（默认只显示有货）",
    )
    s_fetch.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="最多请求页数（调试用；默认拉取全部页）",
    )
    s_fetch.add_argument(
        "--format",
        choices=("text", "json", "csv"),
        default="text",
        help="输出格式",
    )
    s_fetch.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="写入文件；CSV 为 UTF-8 带 BOM（Excel 友好）。可避免 PowerShell 用 > 重定向导致中文乱码",
    )
    s_fetch.set_defaults(_run=run_fetch)

    s_types = sub.add_parser("list-types", help="统计全站 product_type 及数量")
    s_types.set_defaults(_run=run_list_types)

    return p


def main() -> int:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "list-types":
            run_list_types()
        else:
            run_fetch(args)
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误: {e.code} {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"网络错误: {e.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

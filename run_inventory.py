#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按配置文件从多个站点拉取商品目录（Shopify / WooCommerce / Magento / HTML 等适配器），
应用品牌/产品/价格筛选，使用 Frankfurter 汇率折算人民币，并计算税后人民币（默认 50% 关税）。
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
from collections import Counter
from pathlib import Path

from cigar_inventory.pipeline import (
    collect_rows,
    print_csv,
    print_json,
    write_csv,
    write_json,
)
from cigar_inventory.config_loader import load_config


def main() -> int:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="多站点雪茄库存/目录导出（可配置）")
    ap.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.json"),
        help="配置文件路径（JSON），默认 ./config.json",
    )
    ap.add_argument(
        "--format",
        choices=("csv", "json"),
        default="csv",
        help="输出格式",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出文件；CSV 为 UTF-8 BOM。省略则打印到标准输出",
    )
    args = ap.parse_args()

    if not args.config.is_file():
        print(f"找不到配置文件: {args.config.resolve()}", file=sys.stderr)
        print("可复制 config.example.json 为 config.json 后编辑。", file=sys.stderr)
        return 1

    try:
        cfg = load_config(args.config)
        rows = collect_rows(cfg)
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误: {e.code} {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"网络错误: {e.reason}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"配置或数据错误: {e}", file=sys.stderr)
        return 1

    if args.output:
        if args.format == "csv":
            write_csv(args.output, rows)
        else:
            write_json(args.output, rows)
    else:
        if args.format == "csv":
            print_csv(rows)
        else:
            print_json(rows)

    print(f"共 {len(rows)} 条记录。", file=sys.stderr)
    by_site = Counter(r.网站 for r in rows)
    if by_site:
        print("按网站统计（导出条数）:", file=sys.stderr)
        for name, n in sorted(by_site.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {name}: {n}", file=sys.stderr)
    enabled = [s.display_name for s in cfg.sites if s.enabled]
    missing = [n for n in enabled if n not in by_site]
    if missing:
        print(
            "以下已启用站点在结果中无记录（可能被 [跳过]、筛选条件过滤，或抓取为空）:",
            file=sys.stderr,
        )
        for n in missing:
            print(f"  - {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from datetime import datetime
from pathlib import Path

from cigar_inventory.export_report import (
    compare_labels_for_rows,
    compute_new_keys,
    compute_removed_keys,
    find_previous_export,
    load_export_rows_by_key,
    load_row_keys_from_export,
    row_stable_key,
    write_comparison_html,
)
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
        help="输出路径（不含时间戳）；实际写入 {名称}_YYYYMMDD_HHMMSS.{ext}。省略则写入 ./inventory_{时间}.csv",
    )
    ap.add_argument(
        "--print",
        action="store_true",
        dest="to_stdout",
        help="将结果打印到标准输出，不写文件（仍可与同目录历史导出对比并标注「对比」列）",
    )
    ap.add_argument(
        "--no-compare",
        action="store_true",
        help="不与上次导出对比（不写「对比」列、不生成高亮 HTML）",
    )
    ap.add_argument(
        "--no-html",
        action="store_true",
        help="不生成 HTML 对比报告（否则：新增绿色、下架红色）",
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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ".csv" if args.format == "csv" else ".json"
    base_path = args.output if args.output is not None else Path("inventory.csv")
    export_parent = base_path.parent
    export_stem = base_path.stem
    out_file = export_parent / f"{export_stem}_{ts}{suffix}"

    prev_path: Path | None = None
    prev_keys: set[tuple[str, str, str]] | None = None
    had_previous = False
    new_keys: set[tuple[str, str, str]] = set()
    removed_keys: set[tuple[str, str, str]] = set()
    previous_rows_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    compare_labels: list[str] | None = None

    if not args.no_compare:
        prev_path = find_previous_export(export_parent, export_stem, suffix)
        if prev_path is not None:
            prev_keys = load_row_keys_from_export(prev_path)
            had_previous = True
            previous_rows_by_key = load_export_rows_by_key(prev_path)
            new_keys = compute_new_keys(rows, prev_keys)
            current_keys = {row_stable_key(r) for r in rows}
            removed_keys = compute_removed_keys(prev_keys, current_keys)
            compare_labels = compare_labels_for_rows(rows, new_keys, had_previous)
            print(
                f"对比基准: {prev_path.name}（键 {len(prev_keys)}）→ "
                f"新增 {len(new_keys)} 条，下架 {len(removed_keys)} 条。",
                file=sys.stderr,
            )
        else:
            print(
                f"未在 {export_parent.resolve()} 找到上次导出（{export_stem}_*_YYYYMMDD_HHMMSS{suffix}），跳过对比。",
                file=sys.stderr,
            )

    use_compare_col = compare_labels is not None and had_previous

    if args.to_stdout:
        if args.format == "csv":
            print_csv(rows, compare_labels=compare_labels if use_compare_col else None)
        else:
            print_json(rows, compare_labels=compare_labels if use_compare_col else None)
    else:
        export_parent.mkdir(parents=True, exist_ok=True)
        if args.format == "csv":
            write_csv(
                out_file,
                rows,
                compare_labels=compare_labels if use_compare_col else None,
            )
        else:
            write_json(
                out_file,
                rows,
                compare_labels=compare_labels if use_compare_col else None,
            )
        print(f"已写入: {out_file.resolve()}", file=sys.stderr)
        if not args.no_html and not args.no_compare:
            html_path = export_parent / f"{export_stem}_{ts}.html"
            write_comparison_html(
                html_path,
                rows,
                capture_ts=ts,
                previous_path=prev_path,
                new_keys=new_keys,
                removed_keys=removed_keys,
                previous_rows_by_key=previous_rows_by_key,
                had_previous=had_previous,
            )
            print(
                f"已写入 HTML（新增绿色 / 下架红色）: {html_path.resolve()}",
                file=sys.stderr,
            )

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

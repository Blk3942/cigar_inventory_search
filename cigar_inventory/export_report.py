from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

from cigar_inventory.pipeline import CSV_FIELDS, ExportRow

# 与文件名中的时间戳一致：inventory_20260328_143052.csv
_EXPORT_NAME_RE_TEMPLATE = r"^{0}_\d{{8}}_\d{{6}}{1}$"


def row_stable_key(r: ExportRow) -> tuple[str, str, str]:
    """用于跨次导出对比的稳定键（链接 + 规格 + 网站）。"""
    return (
        (r.链接 or "").strip(),
        (r.规格 or "").strip(),
        (r.网站 or "").strip(),
    )


def list_timestamped_exports(parent: Path, base_stem: str, suffix: str) -> list[Path]:
    """同目录下符合 {base_stem}_YYYYMMDD_HHMMSS{suffix} 的文件，按修改时间从新到旧。"""
    if not parent.is_dir():
        return []
    rx = re.compile(_EXPORT_NAME_RE_TEMPLATE.format(re.escape(base_stem), re.escape(suffix)))
    paths = [p for p in parent.iterdir() if p.is_file() and rx.match(p.name)]
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def find_previous_export(parent: Path, base_stem: str, suffix: str) -> Path | None:
    """当前即将写入的新文件尚不存在，取目录内最新一份历史导出。"""
    found = list_timestamped_exports(parent, base_stem, suffix)
    return found[0] if found else None


def load_row_keys_from_csv(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return out
        for row in reader:
            link = (row.get("链接") or "").strip()
            spec = (row.get("规格") or "").strip()
            site = (row.get("网站") or "").strip()
            out.add((link, spec, site))
    return out


def load_row_keys_from_json(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        link = (row.get("链接") or "").strip()
        spec = (row.get("规格") or "").strip()
        site = (row.get("网站") or "").strip()
        out.add((link, spec, site))
    return out


def load_row_keys_from_export(path: Path) -> set[tuple[str, str, str]]:
    suf = path.suffix.lower()
    if suf == ".csv":
        return load_row_keys_from_csv(path)
    if suf == ".json":
        return load_row_keys_from_json(path)
    return set()


def _row_key_from_dict(row: dict[str, str]) -> tuple[str, str, str]:
    link = (row.get("链接") or "").strip()
    spec = (row.get("规格") or "").strip()
    site = (row.get("网站") or "").strip()
    return (link, spec, site)


def load_export_rows_by_key(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    """读取上次导出，按 (链接, 规格, 网站) 聚合为字典（同键多行时保留最后一行）。"""
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    suf = path.suffix.lower()
    if suf == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return out
            for raw in reader:
                slim = {fn: str(raw.get(fn) or "") for fn in CSV_FIELDS}
                k = _row_key_from_dict(slim)
                out[k] = slim
        return out
    if suf == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return out
        if not isinstance(data, list):
            return out
        for item in data:
            if not isinstance(item, dict):
                continue
            slim = {fn: str(item.get(fn) or "") for fn in CSV_FIELDS}
            k = _row_key_from_dict(slim)
            out[k] = slim
        return out
    return out


def compute_new_keys(
    rows: list[ExportRow], previous_keys: set[tuple[str, str, str]],
) -> set[tuple[str, str, str]]:
    """在上次导出键集合基础上，返回本次出现的、上次未出现过的键。"""
    cur = {row_stable_key(r) for r in rows}
    return {k for k in cur if k not in previous_keys}


def compute_removed_keys(
    previous_keys: set[tuple[str, str, str]],
    current_keys: set[tuple[str, str, str]],
) -> set[tuple[str, str, str]]:
    """上次有、本次无的键（视为下架/缺货）。"""
    return previous_keys - current_keys


def compare_labels_for_rows(
    rows: list[ExportRow], new_keys: set[tuple[str, str, str]], had_previous: bool
) -> list[str]:
    if not had_previous:
        return [""] * len(rows)
    return ["新增" if row_stable_key(r) in new_keys else "" for r in rows]


def write_comparison_html(
    path: Path,
    rows: list[ExportRow],
    *,
    capture_ts: str,
    previous_path: Path | None,
    new_keys: set[tuple[str, str, str]],
    removed_keys: set[tuple[str, str, str]],
    previous_rows_by_key: dict[tuple[str, str, str], dict[str, str]],
    had_previous: bool,
) -> None:
    headers = list(CSV_FIELDS) + (["对比"] if had_previous else [])
    esc = html.escape

    summary_parts = [f"本次抓取时间：<strong>{esc(capture_ts)}</strong>"]
    if previous_path is not None:
        summary_parts.append(f"对比基准文件：<code>{esc(previous_path.name)}</code>")
    if had_previous:
        summary_parts.append(
            f"相对上次新增：<strong style=\"color:#0a7a4a\">{len(new_keys)}</strong> 条"
        )
        summary_parts.append(
            f"相对上次下架：<strong style=\"color:#c00\">{len(removed_keys)}</strong> 条"
        )
    else:
        summary_parts.append("未找到符合命名规则的上次导出，未做增删着色。")

    head = (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>库存导出 {esc(capture_ts)}</title>\n"
        "<style>\n"
        "body { font-family: system-ui, sans-serif; margin: 16px; }\n"
        "table { border-collapse: collapse; width: 100%; font-size: 13px; }\n"
        "th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }\n"
        "th { background: #f5f5f5; }\n"
        "tr.new-row td { color: #0a7a4a; font-weight: 600; }\n"
        "tr.removed-row td { color: #c00; font-weight: 600; background: #fff5f5; }\n"
        ".meta { margin-bottom: 12px; color: #333; }\n"
        ".note { font-size: 12px; color: #666; margin-bottom: 8px; }\n"
        "</style>\n</head>\n<body>\n"
        f"<p class=\"meta\">{' · '.join(summary_parts)}</p>\n"
    )
    if had_previous and removed_keys:
        head += (
            "<p class=\"note\">说明：绿色行为本次抓取相对上次<strong>新增</strong>；"
            "表末红色行为上次导出中有、本次抓取中<strong>未再出现</strong>（下架或暂时无货等）。</p>\n"
        )
    head += "<table>\n<thead><tr>"
    for h in headers:
        head += f"<th>{esc(h)}</th>"
    head += "</tr></thead>\n<tbody>\n"

    lines = [head]
    for r in rows:
        key = row_stable_key(r)
        is_new = had_previous and key in new_keys
        tr_cls = ' class="new-row"' if is_new else ""
        lines.append(f"<tr{tr_cls}>")
        for field in CSV_FIELDS:
            val = getattr(r, field, "") or ""
            lines.append(f"<td>{esc(str(val))}</td>")
        if had_previous:
            flag = "新增" if is_new else ""
            lines.append(f"<td>{esc(flag)}</td>")
        lines.append("</tr>\n")

    if had_previous and removed_keys:
        for key in sorted(removed_keys):
            rowd = previous_rows_by_key.get(key)
            if rowd is None:
                continue
            lines.append('<tr class="removed-row">')
            for field in CSV_FIELDS:
                val = rowd.get(field, "") or ""
                lines.append(f"<td>{esc(str(val))}</td>")
            lines.append(f"<td>{esc('下架')}</td>")
            lines.append("</tr>\n")

    lines.append("</tbody>\n</table>\n</body>\n</html>\n")
    path.write_text("".join(lines), encoding="utf-8")

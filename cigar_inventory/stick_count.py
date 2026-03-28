from __future__ import annotations

import re


def extract_cigar_stick_count(spec: str, title: str = "", handle: str = "") -> int | None:
    """
    从规格中解析整盒/整包雪茄支数；无法解析时返回 None。

    若规格为「默认」或为空，会再从标题、handle 中尝试（如 SLB 25、[6] 支装等）。
    若规格有文案但不含可识别数量（如颜色 Silver/Gold），不再用标题推断，避免串规格。
    """
    spec = (spec or "").strip()
    title = (title or "").strip()
    handle = (handle or "").strip()

    n = _parse_count_from_text(spec)
    if n is not None:
        return n

    if _is_default_placeholder(spec) or not spec:
        return _parse_count_from_text(f"{title} {handle}")

    return None


def _is_default_placeholder(spec: str) -> bool:
    s = spec.strip().lower()
    return s in ("默认", "default title", "")


def _parse_count_from_text(text: str) -> int | None:
    if not text or not text.strip():
        return None
    t = text.strip()

    if re.search(r"(?i)\bsingle\s+piece\b", t):
        return _validate_count(1)

    for pat in (
        r"(?i)\b(?:jar|pack|bundle|tray)\s+of\s+(\d+)\b",
        r"(?i)\bbox\s+of\s+(\d+)\b",
    ):
        matches = list(re.finditer(pat, t))
        if matches:
            v = _validate_count(int(matches[-1].group(1)))
            if v is not None:
                return v

    m = re.search(r"\[\s*(\d+)\s*\]", t)
    if m:
        return _validate_count(int(m.group(1)))

    for pat in (
        r"(?i)\bSLB[\s_-]*(\d+)\b",
        r"(?i)\bBN[\s_-]*(\d+)\b",
        r"(?i)\bSLB(\d+)\b",
    ):
        m = re.search(pat, t)
        if m:
            return _validate_count(int(m.group(1)))

    m = re.search(r"(\d+)\s*支", t)
    if m:
        return _validate_count(int(m.group(1)))

    m = re.search(r"(?i)\b(\d+)\s*cigars?\b", t)
    if m:
        return _validate_count(int(m.group(1)))

    return None


def _validate_count(n: int) -> int | None:
    if n < 1 or n > 500:
        return None
    return n

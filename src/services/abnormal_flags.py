"""
Deterministic abnormal-value flagging from extracted lab results.
Compares each value to its printed reference range IN CODE — NOT by LLM.
No interpretive wording is ever generated here.
"""
from __future__ import annotations
import re
from typing import Optional


def _parse_range(range_str: str) -> tuple[Optional[float], Optional[float]]:
    """Parse reference range like '4.0-11.0', '<100', '>12', '70 - 110' into (low, high)."""
    s = str(range_str or "").strip()
    if not s:
        return None, None

    # Try "X - Y" or "X–Y"
    m = re.match(r"^([\d.]+)\s*[-\u2013\u2014]\s*([\d.]+)$", s)
    if m:
        return float(m.group(1)), float(m.group(2))

    # Try "< X" or "<= X"
    m = re.match(r"^[<\u2264]=?\s*([\d.]+)$", s)
    if m:
        return None, float(m.group(1))

    # Try "> X" or ">= X"
    m = re.match(r"^[>\u2265]=?\s*([\d.]+)$", s)
    if m:
        return float(m.group(1)), None

    # Try "Up to X"
    m = re.match(r"(?i)up\s+to\s+([\d.]+)", s)
    if m:
        return None, float(m.group(1))

    return None, None


def _parse_value(val_str: str) -> Optional[float]:
    """Extract numeric value, stripping unit suffixes."""
    s = str(val_str or "").strip()
    m = re.search(r"([\d.]+)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def flag_abnormal_labs(extracted_results: list[dict]) -> list[dict]:
    """
    Compare each lab result to its reference range.
    Returns list of dicts with HIGH/LOW/NORMAL flags. Purely deterministic — no LLM.
    Output per item:
      test_name, value, unit, reference_range, flag (HIGH|LOW|NORMAL), report_date, report_id, source_line
    """
    flagged = []
    for lab in extracted_results:
        test_name = lab.get("test_name") or lab.get("test", "Unknown Test")
        raw_value = lab.get("test_value") or lab.get("value", "")
        unit = lab.get("unit", "")
        ref_range = lab.get("reference_range", "")
        range_note = lab.get("range_note", "")
        report_date = str(lab.get("created_at", ""))[:10]
        report_id = lab.get("report_id", "")
        source_line = lab.get("source_line", "")

        numeric = _parse_value(raw_value)
        low, high = _parse_range(ref_range)

        # Determine flag
        flag = "NORMAL"
        if numeric is not None:
            if low is not None and numeric < low:
                flag = "LOW"
            elif high is not None and numeric > high:
                flag = "HIGH"
        elif range_note:
            # Fallback: trust the range_note from extraction if present
            note_lower = range_note.lower()
            if "above" in note_lower or "high" in note_lower:
                flag = "HIGH"
            elif "below" in note_lower or "low" in note_lower:
                flag = "LOW"

        flagged.append({
            "test_name": test_name,
            "value": raw_value,
            "unit": unit,
            "reference_range": ref_range,
            "flag": flag,
            "report_date": report_date,
            "report_id": report_id,
            "source_line": source_line,
            "is_abnormal": flag in ("HIGH", "LOW"),
        })

    return flagged


def compute_lab_trends(current_results: list[dict], prior_results: list[dict]) -> list[dict]:
    """
    For each test in current_results that also appears in prior_results,
    compute numeric delta. Returns numbers only — no wording about meaning.
    """
    prior_map: dict[str, dict] = {}
    for lab in prior_results:
        name = (lab.get("test_name") or lab.get("test", "")).strip().lower()
        val = _parse_value(lab.get("test_value") or lab.get("value", ""))
        unit = lab.get("unit", "")
        if name and val is not None:
            prior_map[name] = {"value": val, "unit": unit}

    trends = []
    for lab in current_results:
        name = (lab.get("test_name") or lab.get("test", "")).strip().lower()
        unit = lab.get("unit", "")
        cur_val = _parse_value(lab.get("test_value") or lab.get("value", ""))
        if name and cur_val is not None and name in prior_map:
            prev_val = prior_map[name]["value"]
            delta = round(cur_val - prev_val, 3)
            trends.append({
                "test_name": lab.get("test_name") or lab.get("test", ""),
                "previous_value": prev_val,
                "current_value": cur_val,
                "unit": unit,
                "delta": delta,
                "direction": "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged",
            })

    return trends

# -*- coding: utf-8 -*-
"""
Created on Sun Mar 29 19:30:31 2026

@author: chodo
"""

import re
from datetime import datetime, timezone



MISSING_VALUES = {"", "<unknown>", "unknown", "null", "none", "n/a", "nan"}

TIME_CANDIDATE_NAMES = ("time", "timestamp", "epoch")

def extract_header_unit(col_name):
    m = re.search(r"\(([^)]+)\)", col_name)
    if not m:
        return None
    return m.group(1).strip()



def is_missing(value):
    return value is None or str(value).strip().lower() in MISSING_VALUES

def parse_time_value(value):
    """
    Supports:
    - epoch seconds
    - epoch milliseconds
    - ISO-8601
    """
    if is_missing(value):
        return None

    s = str(value).strip()

    if re.fullmatch(r"\d+", s):
        n = int(s)
        try:
            if len(s) >= 13:
                dt = datetime.fromtimestamp(n / 1000.0, tz=timezone.utc)
            else:
                dt = datetime.fromtimestamp(n, tz=timezone.utc)

            if 2000 <= dt.year <= 2026:
                return dt
            return None
        except Exception:
            return None

    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def detect_time_column(fieldnames):
    for name in fieldnames:
        low = name.strip().lower()
        if any(tok in low for tok in TIME_CANDIDATE_NAMES):
            return name
    return None


def infer_column_kind(col_name):
    low = col_name.strip().lower()

    if "time" in low or "epoch" in low or "timestamp" in low:
        return "time"
    if "cpu" in low and ("core" in low or "vcpu" in low):
        return "cpu"
    if "cpu%" in low or low.endswith("%") or "percent" in low:
        return "percent"
    if "memory" in low:
        return "memory"
    if "cost" in low and "hour" in low:
        return "cost_rate"
    if "cost" in low:
        return "cost"
    return "number"

def parse_metric_value(raw_value, col_name):
    """
    Returns dict:
    {
        "raw": raw_value,
        "value": normalized numeric value or None,
        "unit": normalized unit or None,
        "kind": inferred kind,
    }
    """
    kind = infer_column_kind(col_name)
    header_unit = extract_header_unit(col_name)
    header_unit_low = header_unit.lower() if header_unit else None

    if is_missing(raw_value):
        return {"raw": raw_value, "value": None, "unit": None, "kind": kind}

    s = str(raw_value).strip()

    # percentage in value itself
    if s.endswith("%"):
        try:
            return {
                "raw": raw_value,
                "value": float(s[:-1]),
                "unit": "percent",
                "kind": "percent",
            }
        except Exception:
            pass

    # binary memory units in value itself
    mem_match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(Ki|Mi|Gi|Ti)", s)
    if mem_match:
        num = float(mem_match.group(1))
        unit = mem_match.group(2)
        mult = {
            "Ki": 1024,
            "Mi": 1024 ** 2,
            "Gi": 1024 ** 3,
            "Ti": 1024 ** 4,
        }[unit]
        return {
            "raw": raw_value,
            "value": num * mult,
            "unit": "bytes",
            "kind": "memory",
        }

    # decimal memory units in value itself
    dec_match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(K|M|G|T)", s)
    if dec_match and kind == "memory":
        num = float(dec_match.group(1))
        unit = dec_match.group(2)
        mult = {
            "K": 1000,
            "M": 1000 ** 2,
            "G": 1000 ** 3,
            "T": 1000 ** 4,
        }[unit]
        return {
            "raw": raw_value,
            "value": num * mult,
            "unit": "bytes",
            "kind": "memory",
        }

    # millicores in value itself
    milli_match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)m", s)
    if milli_match and kind == "cpu":
        num = float(milli_match.group(1))
        return {
            "raw": raw_value,
            "value": num / 1000.0,
            "unit": "cores",
            "kind": "cpu",
        }

    # plain numeric, interpreted via column/header
    try:
        num = float(s)

        # CPU from header
        if kind == "cpu":
            if header_unit_low in {"vcpu", "cpu", "core", "cores"}:
                return {
                    "raw": raw_value,
                    "value": num,
                    "unit": "cores",
                    "kind": "cpu",
                }
            return {
                "raw": raw_value,
                "value": num,
                "unit": "cores",
                "kind": "cpu",
            }

        # memory from header
        if kind == "memory":
            if header_unit_low == "bytes":
                value = num
            elif header_unit_low == "kb":
                value = num * (1000 ** 1)
            elif header_unit_low == "mb":
                value = num * (1000 ** 2)
            elif header_unit_low == "gb":
                value = num * (1000 ** 3)
            elif header_unit_low == "tb":
                value = num * (1000 ** 4)
            elif header_unit_low == "kib":
                value = num * (1024 ** 1)
            elif header_unit_low == "mib":
                value = num * (1024 ** 2)
            elif header_unit_low == "gib":
                value = num * (1024 ** 3)
            elif header_unit_low == "tib":
                value = num * (1024 ** 4)
            else:
                value = num

            return {
                "raw": raw_value,
                "value": value,
                "unit": "bytes" if header_unit_low else "memory_raw",
                "kind": "memory",
            }

        # cost / cost rate
        if kind == "cost_rate":
            return {
                "raw": raw_value,
                "value": num,
                "unit": "usd_per_hour",
                "kind": "cost_rate",
            }

        if kind == "cost":
            return {
                "raw": raw_value,
                "value": num,
                "unit": "usd" if header_unit_low == "usd" else "cost_raw",
                "kind": "cost",
            }

        # generic numbers
        if kind == "percent":
            return {
                "raw": raw_value,
                "value": num,
                "unit": "percent",
                "kind": "percent",
            }
        if kind == "memory":
            if header_unit_low in {"b", "byte", "bytes"}:
                value = num
            elif header_unit_low == "kb":
                value = num * (1000 ** 1)
            elif header_unit_low == "mb":
                value = num * (1000 ** 2)
            elif header_unit_low == "gb":
                value = num * (1000 ** 3)
            elif header_unit_low == "tb":
                value = num * (1000 ** 4)
            elif header_unit_low == "kib":
                value = num * (1024 ** 1)
            elif header_unit_low == "mib":
                value = num * (1024 ** 2)
            elif header_unit_low == "gib":
                value = num * (1024 ** 3)
            elif header_unit_low == "tib":
                value = num * (1024 ** 4)
            else:
                value = num
        return {
            "raw": raw_value,
            "value": num,
            "unit": "number",
            "kind": kind,
        }

    except Exception:
        return {
            "raw": raw_value,
            "value": None,
            "unit": None,
            "kind": kind,
        }


def summarize_numeric(values):
    vals = [v for v in values if v is not None]
    missing = len(values) - len(vals)

    if not vals:
        return {
            "count": 0,
            "missing": missing,
            "min": None,
            "max": None,
            "mean": None,
            "first": None,
            "last": None,
            "delta": None,
            "num_changes": None,
            "constant": None,
        }

    mean = sum(vals) / len(vals)
    num_changes = sum(1 for i in range(1, len(vals)) if vals[i] != vals[i-1])

    return {
        "count": len(vals),
        "missing": missing,
        "min": min(vals),
        "max": max(vals),
        "mean": mean,
        "first": vals[0],
        "last": vals[-1],
        "delta": vals[-1] - vals[0],
        "num_changes": num_changes,
        "constant": num_changes == 0,
    }

# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 18:15:17 2026

@author: chodo

Usage:
    python .\\plot_json_dates_histogram.py data_dates.json xlsx_dates.json

"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def parse_timestamp(ts: str) -> datetime:
    """
    Parse ISO-like timestamp strings.
    Supports:
    - 2019-03-12T12:58:44+00:00
    - 2019-03-12T12:58:44Z
    - 2025-08-18T07:11:00
    - 2025-08-18 07:11:00
    """
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError as e:
        raise ValueError(f"Unsupported timestamp format: {ts}") from e
    return dt


def normalize_dt(dt: datetime) -> datetime:
    """
    Normalize to second precision.
    If timezone-aware: convert to UTC, then drop tzinfo.
    If naive: keep naive.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0)


def load_top_level_timestamp_keys(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if not isinstance(obj, dict):
        raise ValueError(f"Expected top-level JSON object/dict in {json_path}")

    norm_map = {}
    for raw_key, payload in obj.items():
        if not isinstance(raw_key, str):
            continue
        dt = normalize_dt(parse_timestamp(raw_key))
        norm_map.setdefault(dt, []).append({
            "raw_key": raw_key,
            "payload": payload,
        })
    return norm_map


def make_daily_bins(all_dts):
    if not all_dts:
        return None

    start = min(all_dts).replace(hour=0, minute=0, second=0, microsecond=0)
    end = max(all_dts).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    bins = []
    cur = start
    while cur <= end:
        bins.append(cur)
        cur += timedelta(days=1)
    return bins


def print_match_summary(exact_matches, date_only_overlaps, max_print: int):
    if exact_matches:
        print(f"EXACT TIMESTAMP MATCHES: yes ({len(exact_matches)})")
        for i, dt in enumerate(sorted(exact_matches)):
            if i >= max_print:
                print(f"... and {len(exact_matches) - max_print} more")
                break
            print(f"  {dt.isoformat(sep=' ')}")
    else:
        print("EXACT TIMESTAMP MATCHES: no")

    if date_only_overlaps:
        print(f"DATE-ONLY OVERLAPS: yes ({len(date_only_overlaps)})")
        for i, d in enumerate(sorted(date_only_overlaps)):
            if i >= max_print:
                print(f"... and {len(date_only_overlaps) - max_print} more")
                break
            print(f"  {d.isoformat()}")
    else:
        print("DATE-ONLY OVERLAPS: no")


def save_matches_json(exact_matches, date_only_overlaps, json1_map, json2_map, out_path: str):
    payload = {
        "exact_timestamp_matches": {},
        "date_only_overlaps": [d.isoformat() for d in sorted(date_only_overlaps)],
    }

    for dt in sorted(exact_matches):
        payload["exact_timestamp_matches"][dt.isoformat()] = {
            "json1_entries": json1_map.get(dt, []),
            "json2_entries": json2_map.get(dt, []),
        }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved matches to: {out_path}")


def plot_histogram(dts1, dts2, label1, label2, out_path: str):
    all_dts = dts1 + dts2
    if not all_dts:
        raise ValueError("No timestamps found in either file.")

    bins = make_daily_bins(all_dts)

    plt.figure(figsize=(12, 6))
    plt.hist([dts1, dts2], bins=bins, label=[label1, label2], alpha=0.7)
    plt.xlabel("Date")
    plt.ylabel("Count")
    plt.title("Histogram of timestamps from both JSON files")
    plt.legend()
    plt.xticks(rotation=45)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

    print(f"Saved histogram to: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Plot dates from two JSON files into a histogram and report matches."
    )
    parser.add_argument("json1", help="First JSON file (e.g. your dataset timestamps JSON)")
    parser.add_argument("json2", help="Second JSON file (e.g. xlsx date positions JSON)")
    parser.add_argument(
        "--out",
        default="json_dates_histogram.pdf",
        help="Output histogram image path (default: json_dates_histogram.pdf)",
    )
    parser.add_argument(
        "--matches-out",
        default="json_date_matches.json",
        help="Optional JSON file with exact matches and date overlaps (default: json_date_matches.json)",
    )
    parser.add_argument(
        "--max-print",
        type=int,
        default=50,
        help="Maximum number of matches to print (default: 50)",
    )
    args = parser.parse_args()

    json1_map = load_top_level_timestamp_keys(args.json1)
    json2_map = load_top_level_timestamp_keys(args.json2)

    dts1 = sorted(json1_map.keys())
    dts2 = sorted(json2_map.keys())

    exact_matches = set(dts1).intersection(dts2)
    dates1 = {dt.date() for dt in dts1}
    dates2 = {dt.date() for dt in dts2}
    date_only_overlaps = dates1.intersection(dates2)

    print(f"{Path(args.json1).name}: {len(dts1)} unique normalized timestamps")
    print(f"{Path(args.json2).name}: {len(dts2)} unique normalized timestamps")
    print_match_summary(exact_matches, date_only_overlaps, args.max_print)

    save_matches_json(exact_matches, date_only_overlaps, json1_map, json2_map, args.matches_out)
    plot_histogram(dts1, dts2, Path(args.json1).stem, Path(args.json2).stem, args.out)


if __name__ == "__main__":
    main()
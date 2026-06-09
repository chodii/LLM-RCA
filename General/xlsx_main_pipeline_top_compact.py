# -*- coding: utf-8 -*-
"""
Top-level pipeline for matching source JSON timestamps to XLSX rows.

What it does:
1) extract Excel datetime positions
2) compare source JSON dates vs Excel dates
3) extract candidate rows for overlapped dates
4) score each candidate row by how many source log lines it matches
5) keep the best row, or all tied best rows, for each source timestamp item

Matched row payload is compact:
- keeps matched_source_lines
- keeps the full row
- stores matched_cells as:
    {
      "A": 3,
      "F": 8
    }
  meaning column A matched 3 source lines, column F matched 8 source lines

Expected companion files in the same folder:
- xlsx_extract_dates_rows.py
- xlsx_compare_dates.py
- xlsx_extract_matched_rows_trimmed.py

Usage:
    python ./xlsx_main_pipeline_top_compact.py ^
        "C:/path/to/file.xlsx" ^
        "C:/path/to/source_dates.json"
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List
import os

def load_module(module_path: Path, module_name: str):
    if not module_path.exists():
        raise FileNotFoundError(f"Missing required module: {module_path}")

    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_text(s: Any) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def strip_time_placeholder(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^\s*<time>\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*[-:|]\s*", "", s)
    return s.strip()


def get_line_variants(line: str) -> List[str]:
    variants = []

    raw = normalize_text(line)
    if raw:
        variants.append(raw)

    stripped = normalize_text(strip_time_placeholder(line))
    if stripped and stripped not in variants:
        variants.append(stripped)

    return [v for v in variants if len(v) >= 4]


def extract_text_lines_from_source_item(item: Any) -> List[str]:
    lines: List[str] = []

    if isinstance(item, str):
        if item.strip():
            lines.append(item.strip())
        return lines

    if not isinstance(item, dict):
        return lines

    text_val = item.get("text")
    if isinstance(text_val, list):
        for x in text_val:
            if isinstance(x, str) and x.strip():
                lines.append(x.strip())
    elif isinstance(text_val, str) and text_val.strip():
        lines.append(text_val.strip())

    if lines:
        return lines

    for key, value in item.items():
        if key == "path":
            continue
        if isinstance(value, str) and value.strip():
            lines.append(value.strip())
        elif isinstance(value, list):
            for x in value:
                if isinstance(x, str) and x.strip():
                    lines.append(x.strip())

    return lines


def build_rows_by_date(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    rows_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        for d in row.get("matched_dates", []):
            rows_by_date.setdefault(d, []).append(row)
    return rows_by_date


def score_row_against_source_lines(row: Dict[str, Any], source_lines: List[str]) -> Dict[str, Any]:
    cells = row.get("cells", [])
    if not isinstance(cells, list):
        cells = []

    prepared_lines = []
    for original_line in source_lines:
        variants = get_line_variants(original_line)
        if variants:
            prepared_lines.append((original_line, variants))

    cell_texts = []
    for cell in cells:
        value = cell.get("value")
        if value is None:
            continue
        norm = normalize_text(value)
        if norm:
            cell_texts.append((cell, norm))

    row_blob = " | ".join(norm for _, norm in cell_texts)

    matched_source_lines = []
    matched_cells_count: Dict[str, int] = {}
    seen_lines = set()

    for original_line, variants in prepared_lines:
        hit_columns = set()
        for cell, cell_text in cell_texts:
            if any(v in cell_text for v in variants):
                col = cell.get("column")
                if isinstance(col, str) and col:
                    hit_columns.add(col)

        blob_hit = any(v in row_blob for v in variants)

        if hit_columns or blob_hit:
            if original_line not in seen_lines:
                matched_source_lines.append(original_line)
                seen_lines.add(original_line)

            for col in hit_columns:
                matched_cells_count[col] = matched_cells_count.get(col, 0) + 1

    return {
        "score": len(matched_source_lines),
        "matched_source_lines": matched_source_lines,
        "matched_cells": dict(sorted(matched_cells_count.items())),
        "source_line_count": len(prepared_lines),
    }


def build_final_matches(
    source_json_path: str,
    rows_by_date: Dict[str, List[Dict[str, Any]]],
    matched_date_set,
    mod_compare,
    min_score: int = 1,
    keep_ties: bool = True,
):
    with open(source_json_path, "r", encoding="utf-8") as f:
        source_obj = json.load(f)

    if not isinstance(source_obj, dict):
        raise ValueError("Source JSON must be a dict with timestamp keys.")

    final = {}
    total_row_matches = 0
    matched_timestamp_count = 0

    for raw_ts, payload in source_obj.items():
        if not isinstance(raw_ts, str):
            continue

        normalized_dt = mod_compare.normalize_dt(mod_compare.parse_timestamp(raw_ts))
        source_date = normalized_dt.date().isoformat()

        result_entry = {
            "normalized_timestamp": normalized_dt.isoformat(sep=" "),
            "matched_date": source_date,
            "had_date_overlap": source_date in matched_date_set,
            "matches": [],
        }

        if source_date in matched_date_set:
            candidate_rows = rows_by_date.get(source_date, [])
            payload_items = payload if isinstance(payload, list) else [payload]
            all_scored_matches = []

            for source_index, item in enumerate(payload_items):
                source_lines = extract_text_lines_from_source_item(item)
                if not source_lines:
                    continue

                source_path = item.get("path") if isinstance(item, dict) else None

                for row in candidate_rows:
                    scored = score_row_against_source_lines(row, source_lines)
                    if scored["score"] < min_score:
                        continue

                    all_scored_matches.append(
                        {
                            "source_index": source_index,
                            "source_path": source_path,
                            "score": scored["score"],
                            "source_line_count": scored["source_line_count"],
                            "matched_source_lines": scored["matched_source_lines"],
                            "matched_cells": scored["matched_cells"],
                            "row": row,
                        }
                    )

            if all_scored_matches:
                best_score = max(m["score"] for m in all_scored_matches)
                best_matches = [m for m in all_scored_matches if m["score"] == best_score]
                best_matches = sorted(
                    best_matches,
                    key=lambda x: (
                        -x["score"],
                        x["row"].get("sheet_name", ""),
                        x["row"].get("row", 0),
                    ),
                )

                if keep_ties:
                    result_entry["matches"] = best_matches
                else:
                    result_entry["matches"] = [best_matches[0]]

        if result_entry["matches"]:
            matched_timestamp_count += 1
            total_row_matches += len(result_entry["matches"])

        final[raw_ts] = result_entry

    stats = {
        "source_timestamps": len(final),
        "timestamps_with_date_overlap": sum(1 for v in final.values() if v["had_date_overlap"]),
        "timestamps_with_row_matches": matched_timestamp_count,
        "total_row_matches": total_row_matches,
    }

    return {"stats": stats, "results": final}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the full XLSX pipeline with best-row scoring by matched source log lines."
    )
    parser.add_argument("xlsx_path", help="Path to the Excel workbook (.xlsx)", default=None)
    parser.add_argument("source_json", help="Path to the source JSON whose top-level keys are timestamps", default=None)
    parser.add_argument(
        "--positions-out",
        default="xlsx_date_positions.json",
        help="Intermediate JSON with Excel date-cell positions",
    )
    parser.add_argument(
        "--matches-out",
        default="json_date_matches.json",
        help="Intermediate JSON with date overlaps/matches",
    )
    parser.add_argument(
        "--hist-out",
        default="json_dates_histogram.pdf",
        help="Histogram output path",
    )
    parser.add_argument(
        "--rows-out",
        default="matched_rows_candidates.json",
        help="Intermediate JSON with candidate rows for matched dates",
    )
    parser.add_argument(
        "--final-out",
        default="source_date_row_matches_best.json",
        help="Final output JSON mapping source timestamps to best matched Excel rows",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include empty cells in the intermediate candidate row output",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=1,
        help="Minimum number of matched source lines required for a row match",
    )
    parser.add_argument(
        "--keep-ties",
        action="store_true",
        help="Keep all rows tied for best score instead of only one row",
    )
    args = parser.parse_args()
    return args.xlsx_path, args.source_json, args.positions_out, args.matches_out, args.hist_out, args.rows_out, args.final_out, args.include_empty, args.min_score, args.keep_ties

def main():
    xlsx_path, source_json, _positions_out, _matches_out, _hist_out, _rows_out, _final_out, _include_empty, _min_score, _keep_ties = parse_args()
    api(xlsx_path, source_json, _positions_out, _matches_out, _hist_out, _rows_out, _final_out, _include_empty, _min_score, _keep_ties)

def abs_out_file(base_dir, final_out):
    final_out = str((base_dir / final_out).resolve()) if not Path(final_out).is_absolute() else str(Path(final_out).resolve())
    return os.path.abspath(final_out)

def api(xlsx_path, source_json
        , positions_out="out/xlsx_date_positions.json"
        , matches_out="out/json_date_matches.json"
        , hist_out="out/json_dates_histogram.pdf"
        , rows_out="out/matched_rows_candidates.json"
        , final_out="out/source_date_row_matches_best.json"
        , include_empty=False, min_score=1, keep_ties = False):
    base_dir = Path(__file__).resolve().parent
    (base_dir / "out").mkdir(parents=True, exist_ok=True)
    final_out = abs_out_file(base_dir, final_out)
    if source_json is None or xlsx_path is None:
        if not os.path.exists(final_out):
            raise Exception("Error: the output does not exits")
        return final_out
    mod_extract_positions = load_module(base_dir / "xlsx_extract_dates_rows.py", "xlsx_extract_dates_rows")
    mod_compare = load_module(base_dir / "xlsx_compare_dates.py", "xlsx_compare_dates")
    mod_extract_rows = load_module(base_dir / "xlsx_extract_matched_rows_trimmed.py", "xlsx_extract_matched_rows_trimmed")
    
    xlsx_path = str(Path(xlsx_path).resolve())
    source_json = str(Path(source_json).resolve())
    positions_out = str((base_dir / positions_out).resolve()) if not Path(positions_out).is_absolute() else str(Path(positions_out).resolve())
    matches_out = str((base_dir / matches_out).resolve()) if not Path(matches_out).is_absolute() else str(Path(matches_out).resolve())
    hist_out = str((base_dir / hist_out).resolve()) if not Path(hist_out).is_absolute() else str(Path(hist_out).resolve())
    rows_out = str((base_dir / rows_out).resolve()) if not Path(rows_out).is_absolute() else str(Path(rows_out).resolve())
    
    print("[1/4] Extracting Excel datetime positions...")
    positions = mod_extract_positions.extract_date_positions(xlsx_path)
    with open(positions_out, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, separators=(",", ":"))
    num_dates = len(positions)
    num_positions = sum(len(v) for v in positions.values())
    print(f"Saved {num_positions} positions for {num_dates} unique datetimes to: {positions_out}")

    print("[2/4] Comparing source JSON dates with Excel dates...")
    json1_map = mod_compare.load_top_level_timestamp_keys(source_json)
    json2_map = mod_compare.load_top_level_timestamp_keys(positions_out)

    dts1 = sorted(json1_map.keys())
    dts2 = sorted(json2_map.keys())

    exact_matches = set(dts1).intersection(dts2)
    dates1 = {dt.date() for dt in dts1}
    dates2 = {dt.date() for dt in dts2}
    date_only_overlaps = dates1.intersection(dates2)

    print(f"{Path(source_json).name}: {len(dts1)} unique normalized timestamps")
    print(f"{Path(positions_out).name}: {len(dts2)} unique normalized timestamps")
    mod_compare.print_match_summary(exact_matches, date_only_overlaps, max_print=50)
    mod_compare.save_matches_json(exact_matches, date_only_overlaps, json1_map, json2_map, matches_out)
    mod_compare.plot_histogram(dts1, dts2, Path(source_json).stem, Path(positions_out).stem, hist_out)

    print("[3/4] Extracting candidate rows from Excel for overlapped dates...")
    matched_dates = mod_extract_rows.load_matched_dates(matches_out)
    matched_date_set = {d.isoformat() for d in matched_dates}
    targets_by_sheet_name = mod_extract_rows.load_target_rows_from_positions(positions_out, matched_dates)
    candidate_rows = mod_extract_rows.extract_rows(
        xlsx_path=xlsx_path,
        targets_by_sheet_name=targets_by_sheet_name,
        include_empty=include_empty,
    )
    with open(rows_out, "w", encoding="utf-8") as f:
        json.dump(candidate_rows, f, ensure_ascii=False, indent=2)

    print(f"Matched dates: {len(matched_dates)}")
    print(f"Candidate rows: {len(candidate_rows)}")
    print(f"Saved candidate rows to: {rows_out}")

    print("[4/4] Scoring candidate rows by matched source log lines...")
    rows_by_date = build_rows_by_date(candidate_rows)
    final_payload = build_final_matches(
        source_json_path=source_json,
        rows_by_date=rows_by_date,
        matched_date_set=matched_date_set,
        mod_compare=mod_compare,
        min_score=min_score,
        keep_ties=keep_ties,
    )

    with open(final_out, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)

    stats = final_payload["stats"]
    print(f"Source timestamps: {stats['source_timestamps']}")
    print(f"Timestamps with date overlap: {stats['timestamps_with_date_overlap']}")
    print(f"Timestamps with row matches: {stats['timestamps_with_row_matches']}")
    print(f"Total best-row matches kept: {stats['total_row_matches']}")
    print()
    print("Done.")
    print(f"Final output: {final_out}")
    print(f"Intermediate files: {positions_out}, {matches_out}, {hist_out}, {rows_out}")
    return os.path.abspath(final_out)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

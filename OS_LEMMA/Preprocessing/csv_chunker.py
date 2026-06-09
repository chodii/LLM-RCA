# -*- coding: utf-8 -*-
"""
Created on Sun Mar 29 19:31:20 2026

@author: chodo
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from OS_LEMMA import csv_parser
import log_chunker
import csv

from datetime import timedelta

def skipped_stats_fun(skipped_stats, info, row):
    if info["stripped_length"] > 0:
        skipped_stats["skipped_nonempty_row_count"] += 1
        skipped_stats["skipped_nonempty_lengths"].append(info["stripped_length"])
        skipped_stats["max_skipped_nonempty_length"] = max(
            skipped_stats["max_skipped_nonempty_length"],
            info["stripped_length"]
        )
        if len(skipped_stats["skipped_examples"]) < 5:
            skipped_stats["skipped_examples"].append(row)

def row_non_time_content_stats(row, time_col):
    """
    Inspect non-time cells in a raw CSV row.
    Returns:
        stripped_text: concatenated stripped non-time content
        nonempty_cell_count: how many non-time cells had meaningful content
        stripped_length: length of concatenated meaningful content
    """
    parts = []

    for col, value in row.items():
        if col == time_col:
            continue
        if value is None:
            continue

        s = str(value).strip()
        if not s:
            continue
        if csv_parser.is_missing(s):
            continue

        parts.append(s)

    stripped_text = " ".join(parts)
    return {
        "stripped_text": stripped_text,
        "nonempty_cell_count": len(parts),
        "stripped_length": len(stripped_text),
    }


def read_metrics_csv(csv_path, delimiter=None, skipped_stats={}):
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        if delimiter is None:
            try:
                sample = f.read(4096)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                reader = csv.DictReader(f, dialect=dialect)
            except Exception:
                f.seek(0)
                reader = csv.DictReader(f, delimiter="\t")
        else:
            reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            raise ValueError(f"No columns found in {csv_path}")
        time_col = csv_parser.detect_time_column(fieldnames)

        if not time_col:
            raise ValueError(f"No time column found in {csv_path}")

        for row in reader:
            dt = csv_parser.parse_time_value(row.get(time_col))
            
            if dt is None:
                skipped_stats["skipped_row_count"] += 1
                info = row_non_time_content_stats(row, time_col)
                skipped_stats_fun(skipped_stats, info, row)
                continue
            parsed = {
                "time": dt.isoformat() if dt else None,
                "time_dt": dt,
                "raw": row,
                "metrics": {},
            }
            
            for col in fieldnames:
                if col == time_col:
                    continue
                parsed["metrics"][col] = csv_parser.parse_metric_value(row.get(col), col)
            yield parsed

def chunk_rows_by_time_window(rows, window_seconds):
    """
    Expects rows ordered by time.
    """
    bucket = []
    window_start = None
    window_end = None

    for row in rows:
        dt = row["time_dt"]
        if dt is None:
            continue

        if window_start is None:
            window_start = dt
            window_end = dt + timedelta(seconds=window_seconds)
        if dt > window_end:
            window_start = dt
            window_end = dt + timedelta(seconds=window_seconds)
            if bucket:
                yield bucket
            bucket = []
        bucket.append(row)
    if bucket:
        yield bucket

def build_chunk_json(chunk_rows, source_file, chix):
    if not chunk_rows:
        return None

    metric_columns = list(chunk_rows[0]["metrics"].keys())

    column_metadata = {}
    summary = {}

    for col in metric_columns:
        parsed_cells = [row["metrics"][col] for row in chunk_rows]
        values = [cell["value"] for cell in parsed_cells]

        # first non-null metadata
        unit = next((cell["unit"] for cell in parsed_cells if cell["unit"] is not None), None)
        kind = next((cell["kind"] for cell in parsed_cells if cell["kind"] is not None), None)

        column_metadata[col] = {
            "kind": kind,
            "unit": unit,
        }
        summary[col] = csv_parser.summarize_numeric(values)

    return {
        "source_file": source_file,
        "chunk_index":chix,
        "time_start": chunk_rows[0]["time"],
        "time_end": chunk_rows[-1]["time"],
        "row_count": len(chunk_rows),
        "columns": ["time"] + metric_columns,
        "column_metadata": column_metadata,
        "summary": summary,
        "rows": [
            {
                "time": row["time"],
                "metrics": {
                col: row["metrics"][col]
                for col in metric_columns
            },
                "raw": row["raw"],
            }
            for row in chunk_rows
        ],
    }

#TOP LEVER: 
def chunk_metrics_csv(csv_path, skipped_stats, source_file=None, window_seconds=300, delimiter=None, sort_rows=True):
    rows = list(read_metrics_csv(csv_path, delimiter=delimiter))
    if sort_rows:
        rows.sort(key=lambda r: (r["time_dt"] is None, r["time_dt"]))

    for chix, chunk_rows in enumerate(chunk_rows_by_time_window(rows, window_seconds=window_seconds)):
        yield build_chunk_json(
            chunk_rows,
            source_file=source_file or csv_path
            ,chix=chix
        )
import json
def write_chunk(chunk, fp):
    with open(fp, "w", encoding="utf-8") as jfp:
        json.dump(chunk, jfp)
    
def process_csv_file(fp, nick, src_root, dest_root, files_created):
    skipped_stats = {
        "skipped_row_count": 0,
        "skipped_nonempty_row_count": 0,
        "skipped_nonempty_lengths": [],
        "max_skipped_nonempty_length": 0,
        "skipped_examples": [],
    }
    chunk_sizes = []
    for chunk_index, chunk in enumerate(chunk_metrics_csv(fp, skipped_stats)):
        dest_fp = log_chunker.make_chunk_output_path(dest_root=dest_root, root=src_root, source_fp=fp, chunk_index=chunk_index, nick=nick, files_created=files_created)
        
        files_created.add(dest_fp)
        write_chunk(chunk, dest_fp)
        chunk_sizes.append(len(str(chunk)))
    if skipped_stats["skipped_row_count"]>0:
        print(skipped_stats)
    return chunk_sizes
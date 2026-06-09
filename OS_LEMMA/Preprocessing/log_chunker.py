# -*- coding: utf-8 -*-
"""
Created on Mon Mar 30 00:59:17 2026

@author: chodo

Chunk Lemma-RCA log files into compact DES-like JSON chunks.

Library-first design:
- main public entry point for one file: process_log_file(...)
- optional tree processing: process_log_tree(...)
- CLI main() only wraps the library functions

This module:
- extracts leading ISO timestamp from each row
- prints skipped rows without timestamp (and their stripped length)
- compacts payloads for retrieval
- deduplicates repeating compact rows via log_parser.dedup_rows(...)
- chunks compact rows by count / chars / time span
- handles plain text files and gzip-compressed files
- skips probable binary files
"""

import re
import json
import gzip
import argparse
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, TextIO

import log_parser

import log_proc

DATA_KEY = "data"
FP_KEY = "src"
FILE_NAME_KEY = "file_name"

START_TIME = 0
TEXT = 1
END_TIME = 2
COUNT = 3
SPECIFIC_TIMES = 4

LEADING_TS_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s*(?P<body>.*)$'
)


@dataclass
class LogChunkConfig:
    max_lines: int = 200
    max_chars: int = 24000
    max_span_seconds: int = 600

    print_skipped: bool = False
    max_repeat_span_seconds: int = 3600
    max_repeat_gap_seconds: Optional[int] = None
    log_specific_times: bool = False


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("-r", "--root", required=True, help="Root dataset directory")
    p.add_argument("-d", "--dest", required=True, help="Destination directory for chunk JSON files")
    p.add_argument("--max-lines", type=int, default=200, help="Max rows per chunk")
    p.add_argument("--max-chars", type=int, default=24000, help="Max content_text chars per chunk")
    p.add_argument("--max-span-seconds", type=int, default=600, help="Max time span per chunk")
    p.add_argument("--print-skipped", action="store_true", help="Print skipped rows without timestamp")
    p.add_argument("--skipped-log", default=None, help="Optional file to store skipped rows")
    p.add_argument("--max-repeat-span-seconds", type=int, default=3600,
                   help="Maximum total span for one deduplicated repeat group")
    p.add_argument("--max-repeat-gap-seconds", type=int, default=None,
                   help="Maximum silence between non-consecutive repeats to still merge them")
    p.add_argument("--log-specific-times", action="store_true",
                   help="Store exact occurrence times in compact rows")
    return p.parse_args()


def config_from_args(args) -> LogChunkConfig:
    return LogChunkConfig(
        max_lines=args.max_lines,
        max_chars=args.max_chars,
        max_span_seconds=args.max_span_seconds,
        print_skipped=args.print_skipped,
        max_repeat_span_seconds=args.max_repeat_span_seconds,
        max_repeat_gap_seconds=args.max_repeat_gap_seconds,
        log_specific_times=args.log_specific_times,
    )


def parse_iso_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def is_gzip_file(fp: Path) -> bool:
    try:
        with open(fp, "rb") as f:
            return f.read(2) == b"\x1f\x8b"
    except Exception:
        return False


def open_text_auto(fp: Path):
    if is_gzip_file(fp):
        return gzip.open(fp, "rt", encoding="utf-8", errors="replace", newline="")
    return open(fp, "rt", encoding="utf-8", errors="replace", newline="")


def read_sample_bytes(fp: Path, n: int = 4096) -> bytes:
    try:
        if is_gzip_file(fp):
            with gzip.open(fp, "rb") as f:
                return f.read(n)
        with open(fp, "rb") as f:
            return f.read(n)
    except Exception:
        return b""


def is_probably_text(fp: Path) -> bool:
    sample = read_sample_bytes(fp, 4096)
    if not sample:
        return False
    if b"\x00" in sample:
        return False

    printable = 0
    for b in sample:
        if b in (9, 10, 13) or 32 <= b <= 126:
            printable += 1
    ratio = printable / max(len(sample), 1)
    return ratio >= 0.80


def extract_leading_timestamp(line: str):
    m = LEADING_TS_RE.match(line)
    if not m:
        return None
    ts = parse_iso_utc(m.group("ts"))
    body = m.group("body").strip()
    return ts, body




def make_chunk_output_path(dest_root: Path, root: Path, source_fp: Path, chunk_index: int, nick:str, files_created:set) -> Path:
    rel = Path(source_fp).relative_to(root)
    
    out_dir = dest_root / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    if nick is not None:
        dest_fp= out_dir / f"{rel.name.split('.')[0]}-{nick}-chunk_{chunk_index:05d}.json"
    else:
        dest_fp= out_dir / f"{rel.name.split('.')[0]}-chunk_{chunk_index:05d}.json"
    if dest_fp in files_created:
        raise Exception("File aready present in the dataset")
    files_created.add(dest_fp)
    return dest_fp


def chunk_compact_rows(compact_rows, max_rows=200, max_chars=24000, max_span_seconds=3600):
    """
    compact_rows:
        [start_time, text, end_time, count]
    or
        [start_time, text, end_time, count, [specific_times]]

    Returns:
        list of chunks, each chunk is a list of compact_rows
    """
    chunks = []
    current = []
    current_chars = 0

    for rec in compact_rows:
        rec_end = datetime.fromisoformat(rec[END_TIME])

        text_for_size = rec[TEXT]
        if rec[COUNT] > 1:
            text_for_size += f" [x{rec[COUNT]}]"
        next_chars = current_chars + len(text_for_size) + 40

        should_flush = False
        if current:
            chunk_start = datetime.fromisoformat(current[0][START_TIME])
            span_sec = (rec_end - chunk_start).total_seconds()

            if len(current) >= max_rows:
                should_flush = True
            elif next_chars > max_chars:
                should_flush = True
            elif span_sec > max_span_seconds:
                should_flush = True

        if should_flush:
            chunks.append(current)
            current = []
            current_chars = 0

        current.append(rec)
        current_chars += len(text_for_size) + 40

    if current:
        chunks.append(current)
    return chunks


def write_compact_chunk(out_fp, root: Path, source_fp: Path, chunk_index: int, rows: list):
    start_time = rows[0][START_TIME]
    end_time = rows[-1][END_TIME]

    #content_lines = []
    new_rows =[]
    for r in rows:
    #    line = f"{r[START_TIME]} {r[TEXT]}"
        if r[COUNT] > 1:
    #        line += f" [x{r[COUNT]}]"
            new_rows.append(r)
        else:
            new_rows.append(r[:2])
    #    content_lines.append(line)

    #content_text = "\n".join(content_lines).strip()
    #if not content_text:
    #    content_text = " "

    payload = {
        FP_KEY: str(source_fp),
        #FILE_NAME_KEY: source_fp.name,
        "chunk_index": chunk_index,
        "time_start": start_time,
        "time_end": end_time,
        DATA_KEY: new_rows
        #,"content_text": content_text,
    }

    
    with open(out_fp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return out_fp


def _process_file(fp: Path,
                  root: Path,
                  dest_root: Path,
                  config: LogChunkConfig,
                  skipped_log_handle: Optional[TextIO] = None):
    stats = {
        "chunks_written": 0,
        "kept_rows": 0,
        "compacted_rows": 0,
        "skipped_rows": 0,
        "skipped_nonempty_rows": 0,
        "skipped_nonempty_chars": 0,
    }

    if not is_probably_text(fp):
        return None, stats

    parsed_rows = []

    try:
        with open_text_auto(fp) as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.rstrip("\r\n")
                stripped = raw.strip()

                parsed = extract_leading_timestamp(raw)
                if parsed is None:
                    stats["skipped_rows"] += 1
                    if stripped:
                        stats["skipped_nonempty_rows"] += 1
                        stats["skipped_nonempty_chars"] += len(stripped)

                    msg = f"SKIP\t{fp}\tline={line_no}\tlen={len(stripped)}\t{log_proc.limit_text(stripped, 500)}"
                    if config.print_skipped:
                        print(msg)
                    if skipped_log_handle is not None:
                        skipped_log_handle.write(msg + "\n")
                    continue

                dt, body = parsed
                compact = log_proc.shorten_payload(body)
                parsed_rows.append([dt.isoformat(), compact])
                stats["kept_rows"] += 1

        if not parsed_rows:
            return None, stats

        compact_rows = log_parser.dedup_rows(
            rows=parsed_rows,
            simplify_fn=None,
            max_repeat_span=timedelta(seconds=config.max_repeat_span_seconds),
            max_gap=(
                timedelta(seconds=config.max_repeat_gap_seconds)
                if config.max_repeat_gap_seconds is not None
                else None
            ),
            log_specific_times=config.log_specific_times,
        )

        stats["compacted_rows"] = len(compact_rows)

        chunks = chunk_compact_rows(
            compact_rows,
            max_rows=config.max_lines,
            max_chars=config.max_chars,
            max_span_seconds=config.max_span_seconds,
        )
        
        return chunks, stats
    except Exception as e:
        print(f"ERROR\t{fp}\t{e}")

    return chunks, stats

def process_log_file(fp,
                     nick,
                     root,
                     dest_root,
                     files_created,
                     config: Optional[LogChunkConfig] = None,
                     skipped_log_handle: Optional[TextIO] = None):
    """
    Public library entry point for processing a single log file.

    Parameters:
        fp: source file path
        root: dataset root path, used to preserve relative output structure
        dest_root: destination root for chunk JSON files
        config: optional LogChunkConfig
        skipped_log_handle: optional open file handle for skipped-row logging

    Returns:
        stats dict
    """
    if config is None:
        config = LogChunkConfig()

    fp = Path(fp).resolve()
    root = Path(root).resolve()
    dest_root = Path(dest_root).resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    chunks, stats = _process_file(
        fp=fp,
        root=root,
        dest_root=dest_root,
        config=config,
        skipped_log_handle=skipped_log_handle,
    )
    if chunks is None:
        return stats
    stats["chunk_sizes"] = []
    for chunk_index, chunk in enumerate(chunks):
        out_fp = make_chunk_output_path(dest_root, root, source_fp=fp, chunk_index=chunk_index, nick=nick, files_created=files_created)
        write_compact_chunk(out_fp, root, fp, chunk_index, chunk)
        stats["chunks_written"] += 1
        stats["chunk_sizes"].append(len(str(chunk)))
    return stats




def process_log_tree(root,
                     dest_root,
                     config: Optional[LogChunkConfig] = None,
                     skipped_log_path: Optional[str] = None):
    """
    Optional helper for processing a whole tree with this module alone.
    """
    if config is None:
        config = LogChunkConfig()

    root = Path(root).resolve()
    dest_root = Path(dest_root).resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    summary = {
        "processed_files": 0,
        "chunks_written": 0,
        "kept_rows": 0,
        "compacted_rows": 0,
        "skipped_rows": 0,
        "skipped_nonempty_rows": 0,
        "skipped_nonempty_chars": 0,
    }

    skipped_log_handle = None
    if skipped_log_path:
        skipped_log_handle = open(skipped_log_path, "w", encoding="utf-8")

    try:
        for fp in root.rglob("*"):
            if not fp.is_file():
                continue

            file_stats = process_log_file(
                fp=fp,
                root=root,
                dest_root=dest_root,
                config=config,
                skipped_log_handle=skipped_log_handle,
            )

            if (
                file_stats["chunks_written"] > 0
                or file_stats["kept_rows"] > 0
                or file_stats["skipped_rows"] > 0
            ):
                summary["processed_files"] += 1

            for k in (
                "chunks_written",
                "kept_rows",
                "compacted_rows",
                "skipped_rows",
                "skipped_nonempty_rows",
                "skipped_nonempty_chars",
            ):
                summary[k] += file_stats[k]

    finally:
        if skipped_log_handle is not None:
            skipped_log_handle.close()

    summary_fp = dest_root / "summary.json"
    with open(summary_fp, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    args = parse_args()
    config = config_from_args(args)

    summary = process_log_tree(
        root=args.root,
        dest_root=args.dest,
        config=config,
        skipped_log_path=args.skipped_log,
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
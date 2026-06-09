# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 14:46:55 2026

@author: chodo
"""


pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"
PATH=pth+"TPWSFPGALog.bin"; START=11; REC=32#; W=192512

#!/usr/bin/env python3
import struct
from datetime import datetime, timezone
from collections import Counter

#PATH = "TPWSFPGALog.bin"
START = 11          # you discovered this
REC = 32
INVALID = {0xFFFFFFFF, 0x00000000}

# If time jumps forward by >= this many seconds, we treat it as a new "segment"
# (tune: 3600=1h, 6*3600=6h, 24*3600=1 day)
GAP_SPLIT_SECONDS = 3600#6 * 3600

# Optional: write only valid records into a new file
WRITE_FILTERED = False
OUT_PATH = "TPWSFPGALog.valid.bin"


def dt(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def iter_records(path: str):
    with open(path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        total = (file_size - START) // REC
        for i in range(total):
            f.seek(START + i * REC)
            rec = f.read(REC)
            if len(rec) < REC:
                break
            sec = struct.unpack(">I", rec[0:4])[0]
            yield i, sec, rec
    return

def main():
    total = 0
    valid = 0
    invalid = 0

    min_ts = None
    max_ts = None

    # Collect valid timestamps in ring order start-at-wrap:
    # We'll find the wrap index first by first decrease in sec (including INVALID values).
    secs = []
    for _, sec, _ in iter_records(PATH):
        secs.append(sec)

    total = len(secs)
    wrap_idx = 0
    for i in range(1, total):
        if secs[i] < secs[i - 1]:
            wrap_idx = i
            break

    # Build "chronological-ish" index order (wrap..end, 0..wrap-1)
    order = list(range(wrap_idx, total)) + list(range(0, wrap_idx))

    # Segment detection over VALID timestamps only
    segments = []  # (start_idx_in_order, end_idx_in_order, start_ts, end_ts, count)
    seg_start_pos = None
    seg_start_ts = None
    prev_ts = None
    seg_count = 0

    # For quick sanity, count invalid streaks too
    invalid_runs = 0
    in_invalid_run = False

    # Optional filtered output
    out_f = open(OUT_PATH, "wb") if WRITE_FILTERED else None

    # We need random access to records by index; reopen file
    with open(PATH, "rb") as f:
        for pos, idx in enumerate(order):
            f.seek(START + idx * REC)
            rec = f.read(REC)
            if len(rec) < REC:
                continue
            sec = struct.unpack(">I", rec[0:4])[0]

            if sec in INVALID:
                invalid += 1
                if not in_invalid_run:
                    invalid_runs += 1
                    in_invalid_run = True
                continue
            in_invalid_run = False

            # valid record
            valid += 1
            if out_f:
                out_f.write(rec)

            min_ts = sec if min_ts is None else min(min_ts, sec)
            max_ts = sec if max_ts is None else max(max_ts, sec)

            if seg_start_pos is None:
                seg_start_pos = pos
                seg_start_ts = sec
                prev_ts = sec
                seg_count = 1
                continue

            # If time goes backwards among valid records, that's another session boundary
            # (can happen in ring buffers / mixed boots)
            if sec < prev_ts:
                segments.append((seg_start_pos, pos - 1, seg_start_ts, prev_ts, seg_count))
                seg_start_pos = pos
                seg_start_ts = sec
                prev_ts = sec
                seg_count = 1
                continue

            # Gap-based split
            if (sec - prev_ts) >= GAP_SPLIT_SECONDS:
                segments.append((seg_start_pos, pos - 1, seg_start_ts, prev_ts, seg_count))
                seg_start_pos = pos
                seg_start_ts = sec
                prev_ts = sec
                seg_count = 1
                continue

            prev_ts = sec
            seg_count += 1

        # close final segment
        if seg_start_pos is not None and seg_count > 0:
            segments.append((seg_start_pos, len(order) - 1, seg_start_ts, prev_ts, seg_count))

    if out_f:
        out_f.close()

    print("file:", PATH)
    print("total_records:", total)
    print("wrap_index (file order):", wrap_idx)
    print("valid_records:", valid)
    print("invalid_records:", invalid)
    print("invalid_runs (streaks):", invalid_runs)
    print()

    if min_ts is not None:
        print("valid_time_start:", min_ts, dt(min_ts))
        print("valid_time_end:  ", max_ts, dt(max_ts))
        print("valid_span_sec:  ", max_ts - min_ts)
    else:
        print("No valid timestamps found.")
        return

    print()
    print(f"Segments (split if gap >= {GAP_SPLIT_SECONDS}s or time decreases):")
    for i, (p0, p1, t0, t1, cnt) in enumerate(segments[:30], start=1):
        print(f"{i:02d}. records_in_order[{p0}..{p1}]  n={cnt:7d}  {dt(t0)}  ->  {dt(t1)}  span={t1-t0}s")
    if len(segments) > 30:
        print("... segments total:", len(segments))

    if WRITE_FILTERED:
        print("\nWrote filtered valid records to:", OUT_PATH)


if __name__ == "__main__":
    main()
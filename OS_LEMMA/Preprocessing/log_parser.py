# -*- coding: utf-8 -*-

"""

Created on Mon Mar 30 14:49:42 2026



@author: chodo

"""



from datetime import datetime, timedelta

from typing import Callable, Optional, Sequence, List, Any





def _parse_iso(ts: str) -> datetime:

    """

    Parses ISO timestamps like:

      2025-03-11T08:18:47.049000+00:00

      2024-02-13T10:24:46.497Z

    """

    return datetime.fromisoformat(ts.replace("Z", "+00:00"))





def dedup_rows(

    rows: Sequence[Sequence[str]],

    simplify_fn: Optional[Callable[[str], str]] = None,

    max_repeat_span: Optional[timedelta] = timedelta(hours=1),

    max_gap: Optional[timedelta] = None,

    log_specific_times: bool = False,

) -> List[List[Any]]:

    """

    Deduplicates log rows into compact records.



    Input:

        rows: iterable of [timestamp_iso, text]

              must already be in chronological order

        simplify_fn: optional function to normalize/compact text before grouping

        max_repeat_span:

            maximum total span of one merged group

            - if None: no total-span limit

        max_gap:

            optional maximum silence between two non-consecutive occurrences

            - if None: ignored

        log_specific_times:

            if True, output:

                [start_time, text, end_time, count, [specific_occurrences]]

            else:

                [start_time, text, end_time, count]



    Merge rule:

        A new row merges into an existing group with the same text if:

        - it is consecutive (same normalized text as the immediately previous row), OR

        - it satisfies the non-consecutive window:

              within max_repeat_span from that group's start

              AND within max_gap from that group's last occurrence (if max_gap is set)



        So with:

            max_repeat_span=timedelta(hours=1), max_gap=None

        you get:

            "merge if same text within 1 hour, or if consecutive"



    Returns:

        list of compacted records:

            [start_time, text, end_time, count]

        or

            [start_time, text, end_time, count, [specific_occurrences]]



    Notes:

        - Non-consecutive merging can produce overlapping spans for different texts.

        - This is usually fine for RCA / chunking.

    """

    if simplify_fn is None:

        simplify_fn = lambda x: x



    active = {}   # text -> group

    finished = [] # groups already closed

    prev_text = None

    flush_seq = 0



    def flush_group(text: str) -> None:

        nonlocal flush_seq

        group = active.pop(text, None)

        if group is None:

            return

        group["_flush_seq"] = flush_seq

        flush_seq += 1

        finished.append(group)



    def make_group(ts_iso: str, dt: datetime, text: str) -> dict:

        g = {

            "start_iso": ts_iso,

            "start_dt": dt,

            "text": text,

            "end_iso": ts_iso,

            "end_dt": dt,

            "count": 1,

        }

        if log_specific_times:

            g["specific_occurrences"] = [ts_iso]

        return g



    def update_group(group: dict, ts_iso: str, dt: datetime) -> None:

        if dt > group["end_dt"]:

            group["end_dt"] = dt

            group["end_iso"] = ts_iso

        if dt < group["start_dt"]:

            group["start_dt"] = dt

            group["start_iso"] = ts_iso

        group["count"] += 1

        if log_specific_times:

            group["specific_occurrences"].append(ts_iso)



    def can_merge_nonconsecutive(group: dict, dt: datetime) -> bool:

        if max_repeat_span is not None:

            if dt - group["start_dt"] > max_repeat_span:

                return False

        if max_gap is not None:

            if dt - group["end_dt"] > max_gap:

                return False

        return True



    for row in rows:

        if len(row) < 2:

            raise ValueError(f"Each row must have at least [timestamp, text], got: {row}")



        ts_iso, raw_text = row[0], row[1]

        dt = _parse_iso(ts_iso)

        text = str(simplify_fn(raw_text))



        group = active.get(text)

        is_consecutive = (text == prev_text)



        if group is not None:

            if is_consecutive:

                # Consecutive identical rows always merge.

                update_group(group, ts_iso, dt)

            else:

                if can_merge_nonconsecutive(group, dt):

                    update_group(group, ts_iso, dt)

                else:

                    # Same text exists, but the old group is too old -> close it and start a new one.

                    flush_group(text)

                    active[text] = make_group(ts_iso, dt, text)

        else:

            active[text] = make_group(ts_iso, dt, text)



        # Flush groups that can no longer accept any future NON-consecutive rows.

        # Skip current text, because if the next row is the same text, consecutive merging should still be allowed.

        to_flush = []

        for other_text, other_group in active.items():

            if other_text == text:

                continue



            expired_by_span = (

                max_repeat_span is not None and

                (dt - other_group["start_dt"] > max_repeat_span)

            )

            expired_by_gap = (

                max_gap is not None and

                (dt - other_group["end_dt"] > max_gap)

            )



            if expired_by_span or expired_by_gap:

                to_flush.append(other_text)



        for other_text in to_flush:

            flush_group(other_text)



        prev_text = text



    # Flush whatever remains open.

    for text in list(active.keys()):

        flush_group(text)



    # Keep output order stable and time-based.

    finished.sort(key=lambda g: (g["start_dt"], g["_flush_seq"]))



    out = []

    for g in finished:

        rec = [

            g["start_iso"],

            g["text"],

            g["end_iso"],

            g["count"],

        ]

        if log_specific_times:

            rec.append(g["specific_occurrences"])

        out.append(rec)

        

    return out



def simplify_fn(s: str) -> str:

    return s.replace("<time> ", "").strip()




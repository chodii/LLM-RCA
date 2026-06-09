# -*- coding: utf-8 -*-
"""
Created on Sat Mar 28 00:55:24 2026

@author: chodo
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

from datetime import datetime, timezone

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "oslemma",
    "user": "chody",
    "password": os.environ["MONLIS_DB_PSW"],
}


TABLE_NAME = "lemma_chunks"


def parse_time_arg(ts: str):
    if ts is None:
        return None
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_wordsearch(pattern: str, limit: int = 20):
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end
    FROM {TABLE_NAME}
    WHERE context_text ILIKE %s
    ORDER BY time_start
    LIMIT %s;
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (f"%{pattern}%", limit))
            return cur.fetchall()


def get_fuzzy_search(pattern: str, limit: int = 20):
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end,
           similarity(context_text, %s) AS sim
    FROM {TABLE_NAME}
    WHERE context_text %% %s
    ORDER BY sim DESC, time_start
    LIMIT %s;
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (pattern, pattern, limit))
            return cur.fetchall()


def get_neighbors(source_path: str, chunk_id: int, window: int = 2):
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end
    FROM {TABLE_NAME}
    WHERE source_path = %s
      AND chunk_id BETWEEN %s AND %s
    ORDER BY chunk_id
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (source_path, chunk_id - window, chunk_id + window))
            return cur.fetchall()


def get_records_for_source(source_path: str, limit: int = 20):
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end
    FROM {TABLE_NAME}
    WHERE source_path = %s
    ORDER BY chunk_id
    LIMIT %s
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (source_path, limit))
            return cur.fetchall()


def get_time_range(start_ts, end_ts, limit: int = 20):
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end
    FROM {TABLE_NAME}
    WHERE time_start <= %s
      AND time_end >= %s
    ORDER BY time_start
    LIMIT %s
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (end_ts, start_ts, limit))
            return cur.fetchall()


def get_any_record():
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end
    FROM {TABLE_NAME}
    ORDER BY id
    LIMIT 1
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchone()


def get_record(source_path: str, chunk_id: int):
    query = f"""
    SELECT id, source_path, chunk_id, content_json, context_text, time_start, time_end
    FROM {TABLE_NAME}
    WHERE source_path = %s AND chunk_id = %s
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (source_path, chunk_id))
            return cur.fetchone()


def pretty_print(row):
    if row is None:
        print("No record found.")
        return

    print("=" * 100)
    print(f"id:         {row['id']}")
    print(f"source:     {row['source_path']}")
    print(f"chunk_id:   {row['chunk_id']}")
    print(f"time_start: {row['time_start']}")
    print(f"time_end:   {row['time_end']}")

    context_text = row.get("context_text")
    if context_text:
        print("context_text:")
        print(context_text[:1000])
        if len(context_text) > 1000:
            print("...")

    print("content:")

    content = row["content_json"]
    if isinstance(content, str):
        content = json.loads(content)

    # CSV-style payload from db-loader:
    # {"rows":[{"time":..., "raw":...}, ...]}
    if isinstance(content, dict) and "rows" in content:
        for item in content["rows"]:
            ts = item.get("time")
            raw = item.get("raw")
            print(f"  {ts}  {raw}")
        return

    # LOG-style payload from db-loader:
    # list of records, often [time, normalized_line, ...]
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                ts = item.get("time")
                raw = item.get("raw")
                print(f"  {ts}  {raw}")
            elif isinstance(item, (list, tuple)):
                if len(item) >= 2:
                    ts = item[0]
                    line = item[1]
                    extras = item[2:]
                    if extras:
                        print(f"  {ts}  {line}  extras={extras}")
                    else:
                        print(f"  {ts}  {line}")
                else:
                    print(f"  {item}")
            else:
                print(f"  {item}")
        return

    print(content)


import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="Give me the time, I'll give you files and tell you where to start."
    )
    parser.add_argument(
        "-s", "--time_start",
        dest="time_start",
        type=str,
        default=None,
        help='Time of the first incident (e.g. "2025-03-11T09:15:00+00:00")'
    )
    parser.add_argument(
        "-e", "--time_end",
        dest="time_end",
        type=str,
        default=None,
        help='Time of the last incident (e.g. "2025-03-11T09:15:00+00:00")'
    )

    parser.add_argument(
        "-r", "--root",
        dest="root",
        type=str,
        default=None,
        help="Stored source_path of the chunk."
    )
    parser.add_argument(
        "-d", "--chunk_id",
        dest="chunk_id",
        type=int,
        default=None,
        help="Center chunk id"
    )
    parser.add_argument(
        "-w", "--window",
        dest="window",
        type=int,
        default=2,
        help="Neighbor window size for chunk search"
    )
    parser.add_argument(
        "-l", "--limit",
        dest="limit",
        type=int,
        default=20,
        help="Maximum number of returned rows"
    )

    parser.add_argument(
        "-x", "--exact-find",
        dest="exact",
        type=str,
        default=None,
        help="Find exact match within context_text."
    )

    parser.add_argument(
        "-f", "--fuzzy-find",
        dest="fuzzy",
        type=str,
        default=None,
        help="Find similar text within context_text."
    )

    args = parser.parse_args()

    t0 = parse_time_arg(args.time_start)
    t1 = parse_time_arg(args.time_end)

    return t0, t1, args.root, args.chunk_id, args.window, args.limit, args.exact, args.fuzzy


def main():
    t0, t1, root, cid, window, limit, exact, fuzzy = parse_args()

    all_none = all(x is None for x in (t0, t1, root, cid, exact, fuzzy))

    if all_none:
        print("Default, fetching the first record:")
        row = get_any_record()
        pretty_print(row)
        return

    if t0 is not None and t1 is not None:
        print("Fetching records from given time range")
        res = get_time_range(t0, t1, limit=limit)
        for row in res:
            pretty_print(row)

    if root is not None and cid is not None:
        print("Fetching neighbours of the given chunk.")
        res = get_neighbors(source_path=root, chunk_id=cid, window=window)
        for row in res:
            pretty_print(row)
    elif root is not None:
        print("Fetching records for the given source_path.")
        res = get_records_for_source(source_path=root, limit=limit)
        for row in res:
            pretty_print(row)

    if exact is not None:
        print("Finding by exact word search")
        res = get_wordsearch(exact, limit=limit)
        for row in res:
            pretty_print(row)

    if fuzzy is not None:
        print("Finding by similarity word search")
        res = get_fuzzy_search(fuzzy, limit=limit)
        for row in res:
            pretty_print(row)


if __name__ == "__main__":
    main()
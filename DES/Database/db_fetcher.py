# -*- coding: utf-8 -*-
"""
Created on Sat Mar 28 00:55:24 2026

@author: chodo
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

from datetime import datetime, timedelta
import pytz

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "monlis",
    "user": "chody",
    "password": os.environ["MONLIS_DB_PSW"],
}

def get_wordsearch(pattern:str):
    query=f"""
    SELECT id, source_path, chunk_id, content_json, time_start, time_end
    FROM log_chunks
    WHERE content_text ILIKE '%{pattern}%'
    ORDER BY time_start
    LIMIT 10;
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
"""

"""
def get_fuzzy_search(pattern: str, threshold: float = 0.15, limit: int = 10):
    query = """
        SELECT
            id,
            source_path,
            chunk_id,
            content_json,
            time_start,
            time_end,
            similarity(content_text, %s) AS sim
        FROM log_chunks
        WHERE similarity(content_text, %s) > %s
        ORDER BY sim DESC
        LIMIT %s;
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (pattern, pattern, threshold, limit))
            return cur.fetchall()
        
def exec_query(query, values):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if len(values) == 0:
                cur.execute(query)
            else:
                cur.execute(query, values)
            return cur.fetchall()

def get_file_time_pattern(source_path:str=None
                          , start_ts: str=None
                          , end_ts: str=None
                          , exact_pattern:str=None
                          , elastic_pattern:str=None
                          , limit:int=1):
    qs = []
    qv = []
    query="""
         SELECT source_path, chunk_id, content_json
        """
    # SELECT id, source_path, chunk_id, content_json, time_start, time_end
    qorder = " ORDER BY time_start"
    if elastic_pattern is not None:
        query += f", similarity(content_text, %s) AS sim"
        qv.append(elastic_pattern)
        qs.append(f"similarity(content_text, %s) > %s")
        qv.append(elastic_pattern)
        qv.append(0.01)
        qorder = f" ORDER BY sim DESC"
        #qorder = "ORDER BY sim"
    query += """
         FROM log_chunks
        
        """
    
    if source_path is not None:
        qs.append(" source_path = %s")
        qv.append(source_path)
    
    if start_ts is not None or end_ts is not None:
        qs.append(" has_time = True")
        
        if start_ts is not None:
            qs.append(" time_end >= %s")
            qv.append(start_ts)
            
        if end_ts is not None:
            qs.append(" time_start <= %s")
            qv.append(end_ts)
    
    if exact_pattern is not None:
        qs.append(" content_text ILIKE %s ")
        qv.append(f"%{exact_pattern}%")
        #qv.append(exact_pattern)
    
    if len(qs) > 0:
        query += " WHERE "+qs[0]
    for i in range(1, len(qs), 1):
        query += " AND "+qs[i]
        
    query += qorder
    query += f" LIMIT {limit}"
    query += ";"
    
    return exec_query(query, qv)


def get_neighbors(source_path: str, chunk_id: int, window: int = 2):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, source_path, chunk_id, content_json, time_start, time_end
                FROM log_chunks
                WHERE source_path = %s
                  AND chunk_id BETWEEN %s AND %s
                ORDER BY chunk_id
            """, (source_path, chunk_id - window, chunk_id + window))
            return cur.fetchall()

def get_time_range(start_ts: str, end_ts: str, limit: int = 2):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, source_path, chunk_id, content_json, time_start, time_end
                FROM log_chunks
                WHERE time_start <= %s
                  AND time_end >= %s
                ORDER BY time_start
                LIMIT %s
            """, (end_ts, start_ts, limit))
            return cur.fetchall()

def get_any_record():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, source_path, chunk_id, content_json, time_start, time_end
                FROM log_chunks
                ORDER BY id
                LIMIT 1
            """)
            return cur.fetchone()


def get_record(source_path: str, chunk_id: int):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, source_path, chunk_id, content_json, time_start, time_end
                FROM log_chunks
                WHERE source_path = %s AND chunk_id = %s
            """, (source_path, chunk_id))
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
    print("content:")

    content = row["content_json"]
    if isinstance(content, str):
        content = json.loads(content)

    for ts, line in content:
        print(f"  {ts}  {line}")


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
         help="Time of the first incident (e.g. \"2025-03-11 09:15\")"
    )
    parser.add_argument(
         "-e", "--time_end",
         dest="time_end",
         type=str,
         default=None,
         help="Time of the last incident (e.g. \"2025-03-11 09:15\")"
    )
    
    parser.add_argument(
        "-r", "--root",
        dest="root",
        type=str,
        default=None,
        help="Path to the original file of the chunk."
    )
    parser.add_argument(
         "-d", "--chunk_id",
         dest="chunk_id",
         type=int,
         default=None,
         help="Center chunk id"
    )
    
    parser.add_argument(
        "-x", "--exact-find",
        dest="exact",
        type=str,
        default=None,
        help="Find exact match within the chunk."
    )
    
    parser.add_argument(
        "-f", "--fuzzy-find",
        dest="fuzzy",
        type=str,
        default=None,
        help="Find similar within the chunk."
    )
    
    
    args = parser.parse_args()
    t0=args.time_start
    t1=args.time_end
    if t0 is not None and t1 is not None:
        utc=pytz.UTC
        t0=utc.localize(datetime.fromisoformat(t0))
        t1=utc.localize(datetime.fromisoformat(t1))
    root = args.root
    cid = args.chunk_id
    
    exact= args.exact
    fuzzy = args.fuzzy
    
    return t0, t1, root, cid, exact,fuzzy


def main():
    t0,t1, root,cid, exact,fuzzy = parse_args()
    all_none=True
    for x in (t0, t1, root, cid, exact, fuzzy):
        if x is not None:
            all_none=False
    if all_none:
        print("Default, fetching the first record:")
        row = get_any_record()
        pretty_print(row)
    
    if t0 is not None and t1 is not None:
        print("Fetching records from given time range")
        res = get_time_range(t0, t1)
        for row in res:
            pretty_print(row)
            
    if root is not None:
        print("Fetching neighbours of the given chunk.")
        res = get_neighbors(source_path=root, chunk_id=cid)
        for row in res:
            pretty_print(row)
    
    if exact is not None:
        print("Finding by exact word search")
        res = get_wordsearch(exact)
        for row in res:
            pretty_print(row)
    
    
    if fuzzy is not None:
        print("Finding by similalrity word search")
        res = get_fuzzy_search(fuzzy)
        for row in res:
            pretty_print(row)
            
#"2025-03-11 08:50"
#"2025-03-11 09:00"


#res = get_file_time_pattern(start_ts="2025-03-11T09:15:20Z",end_ts="2025-03-11T09:15:29Z")#exact_pattern="EMERGENCY:MPSPThreads:")
#print(res[0])




if __name__ == "__main__":
    #main()
    ...
    get_file_time_pattern(    start_ts  ="2022-06-01T00:00:00Z"
                                , end_ts="2022-06-01T23:59:59Z"
                                 #,exact_pattern="Orbita Alert"
                                 ,elastic_pattern="Orbita Alert"
                                , limit=10)
    #print(len(res))
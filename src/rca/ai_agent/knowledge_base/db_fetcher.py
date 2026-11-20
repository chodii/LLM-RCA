# -*- coding: utf-8 -*-

"""

Created on Sat Mar 28 00:55:24 2026



@author: chodo

"""

import os

import json

import re

import contextlib

import contextvars

import psycopg2

from psycopg2 import sql

from psycopg2.extras import RealDictCursor



from datetime import datetime, timedelta

import pytz



DB_CONFIG = {

    # A directory (e.g. /var/run/postgresql) selects the Unix socket.
    "host": os.environ.get("DESAI_DB_HOST", "localhost"),

    "port": 5432,

    "dbname": os.environ["DESAI_DBNAME"],

    "user": os.environ["DESAI_USER"],

    "password": os.environ["DESAI_DB_PSW"],

}



def get_wordsearch(pattern:str):

    query="""

    SELECT id, source_path, chunk_id, content_json, time_start, time_end

    FROM log_chunks

    WHERE content_text ILIKE %s

    ORDER BY time_start

    LIMIT 10;

    """

    with psycopg2.connect(**DB_CONFIG) as conn:

        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(query, ("%"+escape_like(pattern)+"%",))

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

        

# Minimum word_similarity() between the similarity_pattern and the best
# matching extent of a chunk for the chunk to be returned. pg_trgm's own
# default is 0.6; 0.4 tolerates small deviations (typos, partial tokens).
# This is a tunable design parameter, not a validated optimum.
WORD_SIMILARITY_THRESHOLD = 0.4

# Hard cap on records per tool call (None = only the model-requested limit).
MAX_LIMIT = None


# similarity_pattern: "|", "," and ";" separate alternatives (boolean OR, as in
# regex and keyword lists); spaces stay part of a phrase. A log phrase that
# itself contains commas still ranks its own chunk first, since that chunk
# matches every part. At most this many distinct alternatives are used per
# call (bounded query cost).
ALTERNATIVE_SEPARATORS = re.compile(r"[|,;]")

MAX_ALTERNATIVES = 8


def split_alternatives(pattern:str) -> list:

    """'ERROR|DMI link, error' -> ['ERROR', 'DMI link'] (trimmed, deduplicated
    case-insensitively, empty parts dropped, capped at MAX_ALTERNATIVES)."""

    alternatives = []

    seen = set()

    for part in ALTERNATIVE_SEPARATORS.split(pattern):

        part = part.strip()

        if not part or part.lower() in seen:

            continue

        seen.add(part.lower())

        alternatives.append(part)

    return alternatives[:MAX_ALTERNATIVES]


def escape_like(pattern:str) -> str:

    """Escape LIKE/ILIKE wildcards so that the pattern is matched literally."""

    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Incident schema used by this thread/context (cached mode, see
# db_loader.ensure_incident_schema); None = the shared public.log_chunks.
CURRENT_SCHEMA = contextvars.ContextVar("desai_incident_schema", default=None)


@contextlib.contextmanager
def use_schema(schema):

    token = CURRENT_SCHEMA.set(schema)

    try:

        yield schema

    finally:

        CURRENT_SCHEMA.reset(token)


def exec_query(query, values, word_similarity_threshold=None):

    with psycopg2.connect(**DB_CONFIG) as conn:

        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            schema = CURRENT_SCHEMA.get()

            if schema is not None:

                # public stays on the path for pg_trgm's functions and operators.
                cur.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema)))

            # Timestamps without an offset (e.g. from the model) are read as UTC,
            # independently of the server's TimeZone setting.
            cur.execute("SET LOCAL TIME ZONE 'UTC';")

            if word_similarity_threshold is not None:
                # Transaction-local setting used by the "<%" operator.
                cur.execute("SELECT set_config('pg_trgm.word_similarity_threshold', %s, true);"
                            , (str(word_similarity_threshold),))

            if len(values) == 0:

                cur.execute(query)

            else:

                cur.execute(query, values)

            return cur.fetchall()



# Two-stage search for several alternatives (word_similarity costs ~0.35 ms
# per 2 kB chunk, so scoring every matching chunk of a large incident for
# every alternative took tens of seconds):
#   1. candidate pool = up to LITERAL_POOL chunks containing the most
#      alternatives literally (cheap ILIKE), plus up to FUZZY_POOL fuzzy
#      matches per alternative (index-supported "<%"; keeps typos and word
#      variants reachable; first matches in load order, ORDER BY id);
#   2. only the pool is scored and ranked.
LITERAL_POOL = 100

FUZZY_POOL = 30


def _filters(source_path=None, start_ts=None, end_ts=None, exact_pattern=None):

    """WHERE conditions shared by every branch of the alternatives query."""

    clauses, values = [], []

    if source_path is not None:

        clauses.append("source_path = %s")

        values.append(source_path)

    if start_ts is not None or end_ts is not None:

        clauses.append("has_time = True")

        if start_ts is not None:

            clauses.append("time_end >= %s")

            values.append(start_ts)

        if end_ts is not None:

            clauses.append("time_start <= %s")

            values.append(end_ts)

    if exact_pattern is not None:

        clauses.append("content_text ILIKE %s")

        values.append("%"+escape_like(exact_pattern)+"%")

    return (" AND ".join(clauses) if clauses else "TRUE"), values


def get_alternatives(alternatives, source_path=None, start_ts=None, end_ts=None
                     , exact_pattern=None, limit=1):

    """OR of several similarity alternatives. A chunk matches if any
    alternative reaches the word_similarity threshold; ranking: number of
    matching alternatives, summed scores, best score (returned as sim)."""

    where, fvalues = _filters(source_path, start_ts, end_ts, exact_pattern)

    qv = []

    likes = ["%"+escape_like(a)+"%" for a in alternatives]

    literal = ("(SELECT id FROM log_chunks WHERE " + where
               + " AND (" + " OR ".join(["content_text ILIKE %s"]*len(likes)) + ")"
               + " ORDER BY (" + " + ".join(["(content_text ILIKE %s)::int"]*len(likes)) + ") DESC"
               + ", time_start, source_path, chunk_id LIMIT %s)")

    qv += fvalues + likes + likes + [LITERAL_POOL]

    fuzzy = []

    for a in alternatives:

        # ORDER BY id = load order: identical in the shared table and the
        # per-incident schemas (physical order depends on the table's history).
        fuzzy.append("(SELECT id FROM log_chunks WHERE " + where + " AND %s <% content_text ORDER BY id LIMIT %s)")

        qv += fvalues + [a, FUZZY_POOL]

    scores = ["s%d" % i for i in range(len(alternatives))]

    # Same comparison as "<%" (real >= the transaction-local threshold).
    thr = "current_setting('pg_trgm.word_similarity_threshold')::real"

    query = ("\n WITH pool AS (" + "\n UNION ".join([literal] + fuzzy) + ")"
             + ",\n scored AS (SELECT c.source_path, c.chunk_id, c.content_json, c.time_start, "
             + ", ".join("word_similarity(%%s, c.content_text) AS %s" % s for s in scores)
             + " FROM log_chunks c JOIN pool USING (id))"
             + "\n SELECT source_path, chunk_id, content_json, GREATEST(" + ", ".join(scores) + ") AS sim"
             + " FROM scored WHERE " + " OR ".join("%s >= %s" % (s, thr) for s in scores)
             + " ORDER BY (" + " + ".join("(%s >= %s)::int" % (s, thr) for s in scores) + ") DESC"
             + ", (" + " + ".join(scores) + ") DESC, sim DESC, time_start, source_path, chunk_id"
             + " LIMIT %s;")

    qv += list(alternatives)

    limit = 1 if limit is None else max(1, int(limit))

    if MAX_LIMIT is not None:

        limit = min(limit, MAX_LIMIT)

    qv.append(limit)

    # psycopg2 %-interpolation: literal "%" in "<%" must be doubled.
    query = query.replace("<% content_text", "<%% content_text")

    return exec_query(query, qv, word_similarity_threshold=WORD_SIMILARITY_THRESHOLD)


def get_file_time_pattern(source_path:str=None

                          , start_ts: str=None

                          , end_ts: str=None

                          , exact_pattern:str=None

                          , elastic_pattern:str=None

                          , limit:int=1):

    alternatives = split_alternatives(elastic_pattern) if elastic_pattern is not None else []

    rows = _search(alternatives, source_path, start_ts, end_ts, exact_pattern, limit)

    if not rows and any(len(a.split()) > 1 for a in alternatives):

        # Keyword-bag fallback: a multi-word pattern that matched nothing as a
        # phrase (e.g. "HMI Redundant Mode Active DMS1 blank reset") is retried
        # once with its words as alternatives (most matching words first).
        words = keyword_alternatives(alternatives)

        if words and words != alternatives:

            rows = _search(words, source_path, start_ts, end_ts, exact_pattern, limit)

    return rows


# Words too common/short to be useful as keyword alternatives.
STOPWORDS = {"the", "and", "for", "with", "from", "after", "before", "upon", "into", "that", "this"
             , "was", "were", "are", "has", "have", "had", "not", "but", "its", "via", "per", "any"
             , "all", "out", "off", "then", "than", "when", "while", "during", "around", "about"}


def keyword_alternatives(alternatives) -> list:

    """Words of the alternatives (punctuation stripped, >= 3 characters, no
    stopwords, deduplicated case-insensitively, at most MAX_ALTERNATIVES)."""

    words, seen = [], set()

    for alternative in alternatives:

        for word in re.split(r"[\s/;:()\[\]\"']+", alternative):

            word = word.strip(".,!?-_")

            key = word.lower()

            if len(word) < 3 or key in STOPWORDS or key in seen:

                continue

            seen.add(key)

            words.append(word)

    return words[:MAX_ALTERNATIVES]


def _search(alternatives, source_path=None, start_ts=None, end_ts=None, exact_pattern=None, limit=1):

    qs = []

    qv = []

    query="""

         SELECT source_path, chunk_id, content_json

        """

    # SELECT id, source_path, chunk_id, content_json, time_start, time_end

    qorder = " ORDER BY time_start, source_path, chunk_id"

    threshold = None

    if len(alternatives) > 1:

        return get_alternatives(alternatives, source_path, start_ts, end_ts, exact_pattern, limit)

    if len(alternatives) == 1:

        # word_similarity() scores the pattern against the best matching
        # extent of the chunk. Whole-string similarity() is dominated by the
        # chunk length (~2000 chars vs. a short pattern) and therefore ranks
        # short chunks first regardless of whether they contain the pattern.
        query += ", word_similarity(%s, content_text) AS sim"

        qv.append(alternatives[0])

        # "<%" = word_similarity(pattern, content_text) >= threshold (GIN index
        # supported). "%%" because psycopg2 uses %-style interpolation.
        qs.append(" %s <%% content_text")

        qv.append(alternatives[0])

        threshold = WORD_SIMILARITY_THRESHOLD

        qorder = " ORDER BY sim DESC, time_start, source_path, chunk_id"

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

        qv.append("%"+escape_like(exact_pattern)+"%")

        #qv.append(exact_pattern)

    

    if len(qs) > 0:

        query += " WHERE "+qs[0]

    for i in range(1, len(qs), 1):

        query += " AND "+qs[i]

        

    query += qorder

    query += " LIMIT %s"

    limit = 1 if limit is None else max(1, int(limit))

    if MAX_LIMIT is not None:

        limit = min(limit, MAX_LIMIT)

    qv.append(limit)

    query += ";"

    return exec_query(query, qv, word_similarity_threshold=threshold)





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



    for entry in content:

        print(f"  {entry[0]}  {entry[-1]}")





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

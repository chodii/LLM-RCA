# -*- coding: utf-8 -*-

"""

Created on Thu Mar 26 01:06:52 2026



@author: chodo

"""



import os, sys


from rca.data_preprocessing import _dataset_walker as walker

import json

from pathlib import Path

from typing import Optional



import psycopg2

from psycopg2 import sql





DB_CONFIG = {

    # A directory (e.g. /var/run/postgresql) selects the Unix socket.
    "host": os.environ.get("DESAI_DB_HOST", "localhost"),

    "port": 5432,

    "dbname": os.environ["DESAI_DBNAME"],

    "user": os.environ["DESAI_USER"],

    "password": os.environ["DESAI_DB_PSW"],

}



from datetime import datetime

def _select_time_span(content):
    t0 = None
    t1 = None

    for entry in content:
        if len(entry) < 2:
            continue

        start = entry[0]
        end = entry[0] if len(entry) == 2 else entry[1]
        if not isinstance(start, str) or not isinstance(end, str):
            continue

        dt_start = datetime.fromisoformat(start)
        dt_end = datetime.fromisoformat(end)

        if t0 is None or t0 > dt_start:
            t0 = dt_start

        if t1 is None or t1 < dt_end:
            t1 = dt_end

    if t0 is not None:
        t0 = t0.isoformat()

    if t1 is not None:
        t1 = t1.isoformat()

    return t0, t1

            

import re

from typing import Any



def clear_str(content:str):
    #content= re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", content)
    #content = content.strip()
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", content)
    content = content.strip()
    return content


def parse_record(obj: dict) -> Optional[dict]:

    """

    Expected JSON format:

    {

        "source": "...",

        "chunk_id": 0,

        "content": [

            ["[TIMESTAMP_A]", "<time> Info ..."],

            ...

        ]

    }

    """

    source_path = obj.get("source")

    chunk_id = obj.get("chunk_id")

    content = obj.get("content")

    if source_path is None or chunk_id is None or not content:

        return None

    cont_new = []

    for cont in content:
        # Keep every field of the entry: collapsed records have the form
        # [time_start, time_end, count, line] and their end time and count
        # must survive (used by the time filter and shown to the agent).
        entry = list(cont)
        if not entry:
            continue
        if isinstance(entry[-1], str):
            entry[-1] = clear_str(entry[-1])
        cont_new.append(entry)

    content = cont_new

    

    t0, t1 = _select_time_span(content)

            

    return {

        "source_path": source_path,

        "chunk_id": int(chunk_id),

        "content_json": json.dumps(content),

        # Searchable log text only; the path is kept in its own column so that
        # exact/similarity patterns cannot match on the file name.
        "content_text": flatten_content(content),

        "time_start": t0,

        "time_end": t1,

        "has_time": t0 is not None

    }





def insert_one(cur, rec: dict) -> None:

    cur.execute(

        """

        INSERT INTO log_chunks (

            source_path,

            chunk_id,

            content_json,

            content_text,

            time_start,

            time_end,

            has_time

        )

        VALUES (

            %(source_path)s,

            %(chunk_id)s,

            %(content_json)s::jsonb,

            %(content_text)s,

            %(time_start)s,

            %(time_end)s,

            %(has_time)s

        )

        ON CONFLICT (source_path, chunk_id)

        DO UPDATE SET

            content_json = EXCLUDED.content_json,

            content_text = EXCLUDED.content_text,

            time_start = EXCLUDED.time_start,

            time_end = EXCLUDED.time_end,

            has_time = EXCLUDED.has_time

        """,

        rec,

    )



def clear_db(cur):

    cur.execute("DELETE FROM log_chunks;")



def _load_files(cur, root, verbose=True):

    """Insert every chunk file under root (walker order) into log_chunks of the
    current search_path. A failing record is undone through its own savepoint.
    Returns (inserted, skipped, skipped_files)."""

    inserted = 0

    skipped = 0

    skipped_files = []

    for fp in walker.iter_spec_files(Path(root),ext="json"):

        try:

            with fp.open("r", encoding="utf-8") as f:

                obj = json.load(f)

        except Exception as e:

            skipped += 1

            skipped_files.append(str(fp))

            if verbose:

                print(f"\rSkipping {fp}: {e}",end="")

            continue

        rec = parse_record(obj)

        if rec is None:

            skipped += 1

            skipped_files.append(str(fp))

            if verbose:

                print(f"\rSkipping malformed JSON record in: {fp}",end="")

            continue

        cur.execute("SAVEPOINT import_record;")

        try:

            insert_one(cur, rec)

        except Exception as e:

            cur.execute("ROLLBACK TO SAVEPOINT import_record;")

            skipped += 1

            skipped_files.append(str(fp))

            if verbose:

                print(f"\rSkipping {fp}: {e}",end="")

            continue

        cur.execute("RELEASE SAVEPOINT import_record;")

        inserted += 1

        if verbose and inserted % 1000 == 0:

            print(f"\rInserted {inserted} records so far...",end="")

    return inserted, skipped, skipped_files



def import_dataset(root, clear_first=True):

    # One transaction for the whole swap: other sessions see either the previous
    # incident or the complete new one. A failing record is undone through its
    # own savepoint; a full rollback here would also undo the DELETE and earlier
    # inserts, leaving another incident's chunks in the table.
    with psycopg2.connect(**DB_CONFIG) as conn:

        with conn.cursor() as cur:

            if clear_first:

                clear_db(cur)

            inserted, skipped, skipped_files = _load_files(cur, root)

        conn.commit()

    print(f"\rDone. Inserted={inserted}, skipped={skipped}",end="")

    if skipped_files:

        print("\nSkipped files:\n  "+"\n  ".join(skipped_files))

    return inserted, skipped



# ---------------------------------------------------------------------------
# Per-incident schemas ("cached" mode): every incident folder is loaded once
# into its own schema inc_<hash>.log_chunks (same table and indexes as
# db_init.sql) and reused by every run. Queries select it via search_path, so
# several incidents can be processed at the same time. A schema is rebuilt only
# when the loading code changes (fingerprint) or the folder changes.

SCHEMA_PREFIX = "inc_"

SCHEMA_DDL = """
CREATE TABLE log_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_path TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    content_json JSONB NOT NULL,
    content_text TEXT NOT NULL,
    time_start TIMESTAMPTZ NULL,
    time_end TIMESTAMPTZ NULL,
    has_time BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK ((has_time = FALSE) OR (has_time = TRUE AND time_start <= time_end)),
    UNIQUE (source_path, chunk_id)
);
CREATE TABLE load_meta (
    fingerprint TEXT NOT NULL,
    chunk_folder TEXT NOT NULL,
    inserted INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    skipped_files JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

SCHEMA_INDEXES = """
CREATE INDEX log_chunks_source_chunk_idx ON log_chunks (source_path, chunk_id);
CREATE INDEX log_chunks_start_time_idx ON log_chunks (time_start);
CREATE INDEX log_chunks_end_time_idx ON log_chunks (time_end);
CREATE INDEX log_chunks_content_text_trgm_idx ON log_chunks USING GIN (content_text public.gin_trgm_ops);
"""


def loader_fingerprint() -> str:

    """Hash of everything that determines a schema's contents."""

    import hashlib
    import inspect

    parts = [inspect.getsource(f) for f in (clear_str, parse_record, _select_time_span, flatten_content
                                            , insert_one, _load_files)]

    return hashlib.sha256("\n".join(parts + [SCHEMA_DDL, SCHEMA_INDEXES]).encode("utf-8")).hexdigest()[:16]


def incident_schema_name(root) -> str:

    import hashlib

    return SCHEMA_PREFIX + hashlib.sha1(os.path.abspath(str(root)).encode("utf-8")).hexdigest()[:16]


def _schema_ready(cur, schema, fingerprint, root):

    cur.execute("SELECT to_regclass(%s)", (schema + ".load_meta",))

    if cur.fetchone()[0] is None:

        return False

    cur.execute(sql.SQL("SELECT fingerprint, chunk_folder FROM {}.load_meta").format(sql.Identifier(schema)))

    row = cur.fetchone()

    return row is not None and row[0] == fingerprint and row[1] == os.path.abspath(str(root))


def ensure_incident_schema(root, verbose=True) -> str:

    """Schema holding the chunks of one incident folder; loaded on first use."""

    schema = incident_schema_name(root)

    fingerprint = loader_fingerprint()

    with psycopg2.connect(**DB_CONFIG) as conn:

        with conn.cursor() as cur:

            if _schema_ready(cur, schema, fingerprint, root):

                return schema

            # Concurrent loaders of the same folder wait here; the second one
            # then finds the finished schema.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (schema,))

            if _schema_ready(cur, schema, fingerprint, root):

                return schema

            t0 = datetime.now()

            if verbose:

                print(f"\nLoading {root} into schema {schema} ...")

            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))

            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

            cur.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema)))

            cur.execute(SCHEMA_DDL)

            inserted, skipped, skipped_files = _load_files(cur, root, verbose=verbose)

            cur.execute(SCHEMA_INDEXES)

            cur.execute("INSERT INTO load_meta (fingerprint, chunk_folder, inserted, skipped, skipped_files)"
                        " VALUES (%s, %s, %s, %s, %s)"
                        , (fingerprint, os.path.abspath(str(root)), inserted, skipped, json.dumps(skipped_files)))

            cur.execute("ANALYZE log_chunks")

        conn.commit()

    if verbose:

        print(f"\rLoaded {schema}: inserted={inserted}, skipped={skipped} ({(datetime.now()-t0).seconds} s)")

    return schema


def preload(incidents_json, split=None, workers=4, verbose=True):

    """Load every incident folder of chunked_incidents.json (optionally only one
    split) into its schema. I/O-bound, so a few threads help."""

    from concurrent.futures import ThreadPoolExecutor

    with open(incidents_json, encoding="utf-8") as fp:

        incidents = list(json.load(fp).values())

    folders = []

    for i, incident in enumerate(incidents):

        validation = (i % 5 == 0)

        if split is None or (split == "validation") == validation:

            folders.append(incident["chunked_destination"])

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:

        schemas = list(pool.map(lambda f: ensure_incident_schema(f, verbose=verbose), folders))

    return dict(zip(folders, schemas))


def flatten_content(content) -> str:

    fltcnt = ""

    for line in content:

        if not line:

            continue

        cnt = line[-1]

        if isinstance(cnt, str):

            fltcnt += cnt+"\n"

        elif isinstance(cnt, list):

            fltcnt += " ".join(str(c) for c in cnt)+"\n"

        elif isinstance(cnt, dict):

            fltcnt += " ".join(f"{k}: {v}" for k, v in cnt.items())+"\n"

        elif cnt is not None:

            fltcnt += str(cnt)+"\n"

    return fltcnt.strip()



def api(root):

    import_dataset(root, clear_first=True)



import argparse

def parse_args():

    parser = argparse.ArgumentParser(

       description="Give me the time, I'll give you files and tell you where to start."

       )

    parser.add_argument(

        "-r", "--root",

        dest="root",

        type=str,

        help="Path to one incident's chunk folder: load it into the shared log_chunks table (legacy swap)"

    )

    parser.add_argument(

        "--preload",

        metavar="CHUNKED_INCIDENTS_JSON",

        help="Load every incident of the file into its own schema (cached mode), once"

    )

    parser.add_argument("--split", choices=("validation", "heldout"), default=None)

    parser.add_argument("--workers", type=int, default=4, help="Parallel loaders for --preload (default 4)")

    args = parser.parse_args()

    if (args.root is None) == (args.preload is None):

        parser.error("give either -r/--root or --preload")

    return args



def main():

    args=parse_args()

    if args.preload:

        schemas = preload(args.preload, split=args.split, workers=args.workers)

        print(f"\n{len(schemas)} incident schemas ready")

    else:

        import_dataset(root=args.root)



if __name__ == "__main__":

    main()

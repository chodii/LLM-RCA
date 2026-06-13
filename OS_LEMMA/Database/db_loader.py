# -*- coding: utf-8 -*-

"""

Created on Thu Mar 26 01:06:52 2026



@author: chodo

"""



import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from DataPreprocessing import _dataset_walker as walker

import json

from pathlib import Path

from typing import Optional



import psycopg2





DB_CONFIG = {

    "host": "localhost",

    "port": 5432,

    "dbname": "oslemma",

    "user": "chody",

    "password": os.environ["MONLIS_DB_PSW"],

}



def parse_content_csv(obj:dict):

    CONTEXT_KEYS = ["columns", "column_metadata", "summary"]

    context = {}

    for k in CONTEXT_KEYS:

        context[k] = obj[k]



    details = {}

    DETAILS_KEY = "rows"

    details[DETAILS_KEY] = [{"time":obj[DETAILS_KEY][ix]["time"], "raw":obj[DETAILS_KEY][ix]["raw"]} for ix in range(len(obj[DETAILS_KEY]))]

    

    return context, details

    

def parse_content_log(obj:dict):

    shortened = [obj["data"][ix][1] for ix in range(len(obj["data"]))]

    return shortened, obj["data"]



def parse_content(obj: dict):

    if "columns" in obj:

        return parse_content_csv(obj)

    if "data" in obj:

        return parse_content_log(obj)

    raise Exception("Unhandeled:",[k for k in obj])



def parse_record(obj: dict) -> Optional[dict]:

    """

    Expected JSON format:

    {

        "source": "...",

        "chunk_id": 0,

        "content": [

            ["2025-03-11T08:18:47.049000+00:00", "<time> Info ..."],

            ...

        ]

    }

    """

    source_path = obj.get("src")

    chunk_id = obj.get("chunk_index")

    time_start = obj.get("time_start")

    time_end = obj.get("time_end")

    

    context, details = parse_content(obj)

    if source_path is None or chunk_id is None or not context:

        return None



    return {

        "source_path": source_path,

        "chunk_id": int(chunk_id),

        "content_json": json.dumps(details),

        "context_text": flatten_content(context),

        "time_start": time_start,

        "time_end": time_end,

    }





def insert_one(cur, rec: dict) -> None:

    cur.execute(

        """

        INSERT INTO lemma_chunks (

            source_path,

            chunk_id,

            content_json,

            context_text,

            time_start,

            time_end

        )

        VALUES (

            %(source_path)s,

            %(chunk_id)s,

            %(content_json)s::jsonb,

            %(context_text)s,

            %(time_start)s,

            %(time_end)s

        )

        ON CONFLICT (source_path, chunk_id)

        DO UPDATE SET

            content_json = EXCLUDED.content_json,

            time_start = EXCLUDED.time_start,

            time_end = EXCLUDED.time_end

        """,

        rec,

    )





def import_dataset(root):

    CHUNK_DIR = Path(root)

    inserted = 0

    skipped = 0



    with psycopg2.connect(**DB_CONFIG) as conn:

        with conn.cursor() as cur:

            for fp in walker.iter_spec_files(CHUNK_DIR,ext="json"):

                try:

                    with fp.open("r", encoding="utf-8") as f:

                        obj = json.load(f)



                    rec = parse_record(obj)

                    if rec is None:

                        skipped += 1

                        print(f"Skipping malformed JSON record in: {fp}")

                        continue



                    insert_one(cur, rec)

                    inserted += 1



                    if inserted % 1000 == 0:

                        conn.commit()

                        print(f"Inserted {inserted} records so far...")



                except Exception as e:

                    conn.rollback()

                    skipped += 1

                    print(f"Skipping {fp}: {e}")

            conn.commit()

    print(f"Done. Inserted={inserted}, skipped={skipped}")



def flatten_content(content) -> str:

    return "\n".join(str(line) for line in content)



import argparse

def parse_args():

    parser = argparse.ArgumentParser(

       description="Give me the time, I'll put it in the db."

       )

    parser.add_argument(

        "-r", "--root",

        dest="root",

        type=str,

        help="Path to the root folder"

    )

    args = parser.parse_args()

    root=args.root

    return root



def main():

    root=parse_args()

    import_dataset(root=root)



if __name__ == "__main__":

    main()
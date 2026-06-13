# -*- coding: utf-8 -*-

"""

Created on Thu Mar 26 01:06:52 2026



@author: chodo

"""



import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from DataPreprocessing import _dataset_walker as walker

import json

from pathlib import Path

from typing import Optional



import psycopg2





DB_CONFIG = {

    "host": "localhost",

    "port": 5432,

    "dbname": "monlis",

    "user": "chody",

    "password": os.environ["MONLIS_DB_PSW"],

}



from datetime import datetime

def _select_time_span(content):

    t0 = None

    t1 = None

    if content[-1][0] is not None:# if any has, the last will have

        for i in range(len(content)):

            dt_start = datetime.fromisoformat(content[i][0])

            dt_end = datetime.fromisoformat(content[i][0] if len(content[i])==2 else content[i][1])

            if t0 is None or t0>dt_start:

                t0 = dt_start

            if t1 is None or t1<dt_end:

                t1 = dt_end

    if t0 is not None:

        t0 = t0.isoformat()

    if t1 is not None:

        t1 = t1.isoformat()

    return t0, t1

            

import re

from typing import Any



def clear_str(content:str):

    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", content)



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

    source_path = obj.get("source")

    chunk_id = obj.get("chunk_id")

    content = obj.get("content")

    cont_new = []

    for cont in content:

        cont_new.append([cont[0], clear_str(cont[-1])])

    content = cont_new

    if source_path is None or chunk_id is None or not content:

        return None

    

    t0, t1 = _select_time_span(content)

            

    return {

        "source_path": source_path,

        "chunk_id": int(chunk_id),

        "content_json": json.dumps(content),

        "content_text": source_path+"\n"+flatten_content(content),

        "time_start": t0,

        "time_end": t1,

        "has_time": content[-1][0] is not None

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



def import_dataset(root, clear_first=True):

    CHUNK_DIR = Path(root)

    inserted = 0

    skipped = 0



    with psycopg2.connect(**DB_CONFIG) as conn:

        with conn.cursor() as cur:

            if clear_first:

                clear_db(cur)

            for fp in walker.iter_spec_files(CHUNK_DIR,ext="json"):

                try:

                    with fp.open("r", encoding="utf-8") as f:

                        obj = json.load(f)



                    rec = parse_record(obj)

                    if rec is None:

                        skipped += 1

                        print(f"\rSkipping malformed JSON record in: {fp}",end="")

                        continue

                    # clean

                    insert_one(cur, rec)

                    inserted += 1



                    if inserted % 1000 == 0:

                        conn.commit()

                        print(f"\rInserted {inserted} records so far...",end="")



                except Exception as e:

                    conn.rollback()

                    skipped += 1

                    print(f"\rSkipping {fp}: {e}",end="")

            conn.commit()

    print(f"\rDone. Inserted={inserted}, skipped={skipped}",end="")



def flatten_content(content) -> str:

    fltcnt = ""

    for line in content:

        cnt = line[-1]

        if type(cnt) == list:

            fltcnt += cnt+"\n"

        elif type(cnt) == dict:

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
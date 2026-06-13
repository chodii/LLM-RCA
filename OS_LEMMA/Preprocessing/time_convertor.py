# -*- coding: utf-8 -*-

"""

Created on Sun Mar 29 17:39:11 2026



@author: chodo

"""



from datetime import datetime, timezone

import csv



def parse_unix_time(value: str):

    """

    Convert Unix timestamp in seconds to ISO-8601 UTC string.

    Returns None if parsing fails.

    """

    try:

        ts = int(value)

        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    except Exception:

        return None





def iter_csv_rows_with_normalized_time(csv_path, delimiter="\t"):

    """

    Reads a TSV/CSV file and yields each row with normalized time added

    under key 'time_iso'.

    """

    with open(csv_path, "r", encoding="utf-8", newline="") as f:

        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:

            raw_time = row.get("Time")

            row["time_iso"] = parse_unix_time(raw_time) if raw_time else None

            yield row



def parse_time_unix_seconds(value):

    if value in (None, "", "<unknown>"):

        return None

    return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()



def parse_cpu_cores(value):

    if value in (None, "", "<unknown>"):

        return None

    if value.endswith("m"):

        return float(value[:-1]) / 1000.0

    return float(value)



def parse_percent(value):

    if value in (None, "", "<unknown>"):

        return None

    return float(value.rstrip("%"))



def parse_memory_bytes(value):

    if value in (None, "", "<unknown>"):

        return None



    units = {

        "Ki": 1024,

        "Mi": 1024**2,

        "Gi": 1024**3,

        "Ti": 1024**4,

        "K": 1000,

        "M": 1000**2,

        "G": 1000**3,

        "T": 1000**4,

    }



    for suffix, mult in units.items():

        if value.endswith(suffix):

            return int(float(value[:-len(suffix)]) * mult)



    return int(float(value))



def iter_metrics_csv(csv_path, delimiter="\t"):

    with open(csv_path, "r", encoding="utf-8", newline="") as f:

        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:

            yield {

                "time": parse_time_unix_seconds(row.get("Time")),

                "cpu_cores": parse_cpu_cores(row.get("CPU(cores)")),

                "cpu_percent": parse_percent(row.get("CPU%")),

                "memory_bytes": parse_memory_bytes(row.get("MEMORY(bytes)")),

                "memory_percent": parse_percent(row.get("MEMORY%")),

                "raw": row,

            }
# -*- coding: utf-8 -*-

"""

Created on Wed Jan 28 19:34:16 2026



@author: chodo

"""



#!/usr/bin/env python3

import sys

from pathlib import Path

from collections import defaultdict



def normalize_extension(path: Path) -> str:

    """

    Normalize extensions so rotated logs stay together:

      hmi_runtime.log.bkp.1  -> .log

      hmi_runtime.log.2.gz   -> .log.gz

      TPWSFPGALog.bin        -> .bin

    """

    name = path.name.lower()



    # Compressed rotated logs

    if ".log" in name and name.endswith(".gz"):

        return ".log.gz"



    # Any rotated log variant

    if ".log" in name:

        return ".log"



    # Otherwise normal extension

    return path.suffix.lower() if path.suffix else "<no_ext>"



def human_size(n: int) -> str:

    for unit in ["B", "KB", "MB", "GB", "TB"]:

        if n < 1024:

            return f"{n:.2f} {unit}"

        n /= 1024

    return f"{n:.2f} PB"



def main() -> int:

    if len(sys.argv) != 2:

        print("Usage: analyze_file_types.py /path/to/dataset", file=sys.stderr)

        return 2



    root = Path(sys.argv[1]).expanduser().resolve()

    if not root.is_dir():

        print(f"ERROR: Not a directory: {root}", file=sys.stderr)

        return 2



    counts = defaultdict(int)

    sizes = defaultdict(int)



    for p in root.rglob("*"):

        if not p.is_file():

            continue

        try:

            size = p.stat().st_size

        except OSError:

            continue



        ext = normalize_extension(p)

        counts[ext] += 1

        sizes[ext] += size



    # Sort by total size descending

    rows = sorted(

        counts.keys(),

        key=lambda k: sizes[k],

        reverse=True

    )



    print(f"{'EXTENSION':15s} {'FILES':>10s} {'TOTAL SIZE':>15s}")

    print("-" * 45)

    for ext in rows:

        print(f"{ext:15s} {counts[ext]:10d} {human_size(sizes[ext]):>15s}")



    print("-" * 45)

    print(f"{'TOTAL':15s} {sum(counts.values()):10d} {human_size(sum(sizes.values())):>15s}")



    return 0



if __name__ == "__main__":

    raise SystemExit(main())




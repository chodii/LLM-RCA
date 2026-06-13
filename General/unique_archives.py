# -*- coding: utf-8 -*-

"""

Created on Wed Mar 18 22:41:54 2026



@author: chodo

"""



import os



interesting = {"7z", "gz", "zip", "bkp", "old", "0", "1", "2", "3", "4", "5"}



def find_archive_candidates(root_dir):

    matches = []



    for dirpath, _, filenames in os.walk(root_dir):

        for filename in filenames:

            parts = filename.split(".")

            if len(parts) < 2:

                continue



            exts = {p.lower() for p in parts[1:] if p}

            if exts & interesting:

                matches.append(os.path.join(dirpath, filename))



    return matches





import sys

def main():

    if len(sys.argv) != 2:

        print("Usage: find_archives.py /path/to/dataset", file=sys.stderr)

        return 2

    root = sys.argv[1]

    unique_type_combinations = set()

    for path in find_archive_candidates(root):

        parts = path.split(".")

        if len(parts) < 2:

            continue

        ending = path[len(parts[0]):]

        if ending not in unique_type_combinations:

            unique_type_combinations.add(ending)

    print(unique_type_combinations)

if __name__ == "__main__":

    raise SystemExit(main())
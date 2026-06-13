# -*- coding: utf-8 -*-

"""

Created on Wed Mar 18 22:37:49 2026



@author: chodo

"""



import os



def find_unique_formats(root_dir):

    unique_formats = set()



    for dirpath, _, filenames in os.walk(root_dir):

        for filename in filenames:

            parts = filename.split(".")



            # skip files with no extension

            if len(parts) < 2:

                continue



            # take everything after the first dot

            for ext in parts[1:]:

                if ext:

                    unique_formats.add(ext.lower())



    return unique_formats



import sys

def main():

    if len(sys.argv) != 2:

        print("Usage: unique_ff.py /path/to/dataset", file=sys.stderr)

        return 2

    root = sys.argv[1]

    formats = find_unique_formats(root)



    print("Unique file formats found:")

    for fmt in sorted(formats):

        print(fmt)



if __name__ == "__main__":

    raise SystemExit(main())
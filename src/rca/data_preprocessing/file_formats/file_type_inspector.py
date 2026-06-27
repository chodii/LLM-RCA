# -*- coding: utf-8 -*-

"""

Created on Fri Feb 20 20:14:08 2026



@author: chodo

"""

import os

from rca.data_preprocessing import _dataset_walker

def find_existing(root, ft, amount=10):

    found = 0

    empty = 0

    for fp in _dataset_walker.dataset_iterator(root):

        suffixes = _dataset_walker.parse_suffixes(fp)

        if ft in suffixes:

            found += 1

            size = os.path.getsize(fp)

            peek = "x"*10

            if size > 0:

                with open(fp, "rb") as f:
                    peek_bytes = f.read(amount)

                peek = peek_bytes.decode("utf-8", errors="replace")

                print("\n" + peek, "\t", size, "\t", fp[len(root):])

            else:

                empty += 1
                
    print("-"*10)

    print(found, "files matched with considered suffixes\t out of which", empty, "were none")

import argparse

def parse_arg():

    parser = argparse.ArgumentParser(prog="File type inspector", description="This program tells you distinct file types in your dataset.")

    parser.add_argument('-r',"--root",dest="root", type=str, default="C:\\Datasets\\DESu\\", help="Source folder of your dataset.")

    parser.add_argument('-i', "--inspect", dest="inspect", type=str, default=None, help="Inspect a specific file type, and print all locations of this file type. Use as: -i <type> or -i \"None\" if you want to view files without any suffix.")

    parser.add_argument('-a', "--amount", dest="amount", type=int, default=10)

    

    return parser.parse_args()



def main():

    args=parse_arg()

    root = args.root

    file_type = args.inspect if args.inspect != "None" else None

    amount = args.amount

    print(root, file_type, amount)

    print("--------")

    find_existing(root, file_type, amount=amount)

    

    

if __name__ == "__main__":

    main()
# -*- coding: utf-8 -*-

"""

Created on Thu Feb 19 16:20:52 2026



@author: chodo

"""

import sys

import os






from rca.data_preprocessing import _dataset_walker



class Suffix_Counter:

    def __init__(self):

        self.combinations = {}

        self.distinct   = {}

    

    def _update_combinations(self, fp):

        dirs = fp.split("\\")

        if len(dirs) == 1:

            return

        parts = dirs[-1].split(".", 1)

        suffix = None

        if not len(parts) == 1:

            suffix = parts[1]

        if suffix not in self.combinations:

            self.combinations[suffix] = 1

            return

        self.combinations[suffix] += 1

    

    def _update_distinct(self, fp):

        dirs = fp.split("\\")

        if len(dirs) == 1:

            return

        parts = dirs[-1].split(".")

        suffixes = [None]

        if not len(parts) == 1:

            suffixes = parts[1:]

        for suffix in suffixes:

            if suffix not in self.distinct:

                self.distinct[suffix] = 1

                continue

            self.distinct[suffix] += 1

        

    def process_dataset(self, root):

        for fp in _dataset_walker.dataset_iterator(root):

            self._update_combinations(fp)

            self._update_distinct(fp)

        print("combinations:",self.combinations)

        print("\ndistinct:", self.distinct)



import argparse

def parse_arg():

    parser = argparse.ArgumentParser(prog="File type scout.", description="This program tells you distinct file types in your dataset.")

    parser.add_argument('-r',"--root",dest="root", type=str, default="C:\\Datasets\\DESu\\", help="Source folder of your dataset.")    

    return parser.parse_args()



def main():

    args=parse_arg()

    root = args.root

    sc = Suffix_Counter()

    sc.process_dataset(root)



if __name__ == "__main__":

    main()
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 29 18:07:16 2026

@author: chodo
"""


import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from datetime import datetime, timedelta

import pytz

import OSLEMMA_Chunker as chunker

#import Chunking.chunker
#import Visualizations.hist as Viz_Hist

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
    parser.add_argument(
         "-o", "--dest",
         dest="dest",
         type=str,
         help="Path to the destination folder"
    )
    parser.add_argument(
         "-t", "--time",
         dest="time",
         type=str,
         default=None,
         help="Time of the incident (e.g. \"2025-03-11 09:15\")"
    )
    parser.add_argument(
         "-s", "--chunk_size",
         dest="chunk_size",
         default=500,
         type=int,
         help="Target chunk size"
    )
    
    args = parser.parse_args()
    root=args.root
    dest=args.dest
    chunk_size=args.chunk_size
    time = args.time
    if time is not None:
        utc=pytz.UTC
        time=utc.localize(datetime.fromisoformat(time))
        time_end = time + timedelta(minutes=10)
        time_start = time - timedelta(minutes=60)
    else:
        time_end = None
        time_start = None
    return root, dest#, time_start, time_end, chunk_size





def main():
    root, dest = parse_args()
    chunker.chunk_dataset(src=root, dest=dest)
    print("Chunking done")
    
if __name__ == "__main__":
    main()
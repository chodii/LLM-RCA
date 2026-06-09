# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 00:50:41 2026

@author: chodo
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import DataPreprocessing.Window.WindowedDataSelection as WindowedDataSelection
from DataPreprocessing.Window import TextSniffer

import argparse
from datetime import datetime, timedelta

import pytz

import Chunking.chunker
import Visualizations.hist as Viz_Hist

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
    return root, dest, time_start, time_end, chunk_size

DES_ANOMALY_MARKERS={
    # marker: severity (max=0, min=inf)
    "EMERGENCY:MPSPThreads::Restart":0
    #, "Failure":5
    #, "Error":10
    #, "Warning":30    
    }
SEVERITY_KEY = "severity"
FOLDER_PREPROCESSED="windowed_selection"
FOLDER_CHUNKED="chunked_"

def identify_anomalies(src):
    incidence_list = {}
    unique_dates = set()
    for k in DES_ANOMALY_MARKERS:
        _dates, events = TextSniffer.find_events(k, root=src)
        for d in _dates:# copy the dates
            unique_dates.add(d)
        for t in events:# copy the events
            if t not in incidence_list:
                incidence_list[t]=[]
            events_of_log = events[t]
            for event in events_of_log:
                event[SEVERITY_KEY] = DES_ANOMALY_MARKERS[k]
            incidence_list[t] = events_of_log
    sorted_events = dict(sorted(events.items()))
    return sorted_events

def line_lens_analysis_api(dest_root, ts_mark, time_start, time_end):
    _, winsel_dest = decide_destination(dest_root,ts_mark, time_start, time_end)
    if (not os.path.exists(winsel_dest)):
        raise Exception("\nError: Doestination does not exist!")
    line_lengths = Chunking.chunker.line_lengths(winsel_dest)
    return line_lengths

def decide_destination(dest,ts_mark, time_start, time_end):
    if time_start is not None and time_end is not None:
        dest = dest+ts_mark.replace(":","-")
    else:
        dest = dest+"None"
    winsel_dest = os.path.join(dest,FOLDER_PREPROCESSED)
    return dest, winsel_dest

def api(root, dest
        , time_start, time_end
        ,ts_mark, chunk_size, INCLUDE_STATIC_FILES=False
        , override=False, anom_detect=False, LIMIT_CONTENT=True):
    dest, winsel_dest = decide_destination(dest,ts_mark, time_start, time_end)
    if override or (not os.path.exists(dest)):
        #print("Selecting\n")
        #winsel_dest = 
        WindowedDataSelection.extract_subset_json(root
                                                , time_end
                                                , time_start
                                                , dest=winsel_dest
                                                , INCLUDE_STATIC_FILES=INCLUDE_STATIC_FILES)#                                            
    if anom_detect:
        #print("Identifying anomalies within the time window")
        anomalies = identify_anomalies(src=winsel_dest)
        #print("Anomalies detected:",len(anomalies))
    else:
        anomalies = []        
    chunk_dest = os.path.join(dest,FOLDER_CHUNKED+str(chunk_size))
    chunk_sizes, after_dedu = Chunking.chunker.chunk_dataset(src=winsel_dest
                                                 , dest=chunk_dest
                                                 , max_chunk_len=chunk_size
                                                 , LIMIT_CONTENT=LIMIT_CONTENT)
    return chunk_sizes, anomalies, chunk_dest, after_dedu

def main():
    root, dest, time_start, time_end, chunk_size = parse_args()
    chunk_sizes, _, _ = api(root, dest, time_start, time_end, chunk_size)
    
    Viz_Hist.hist_from_array(chunk_sizes, x="chunk sizes", y="numbers", title="Real Chunk Sizes", show=True)
    print("\t ",len(chunk_sizes), "chunks created", end="")
    # (Build time-dependency graph (of all)
    # Build AI agent
    #   - reasoning
    #   - MCP
    ...
    
    
if __name__ == "__main__":
    main()
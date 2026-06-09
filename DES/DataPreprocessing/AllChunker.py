# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 00:17:42 2026

@author: chodo
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#print("pp",os.path.dirname(__file__))
import argparse
import json
from datetime import datetime, timedelta

from DataPreprocessing import DESAnalyst
from DataPreprocessing import Matchmaker
from DataPreprocessing.Visualizations import time_diffs

from DataPreprocessing.Visualizations import line_lengths_hists
from DataPreprocessing.Evaluation import evaluate_IR
MIN_SCORE = 8
def get_incident_root(root, match, ts, DEPTH=3):
    root_parts = match.get("source_path").replace(root, "").split("\\")
    incident_root = root
    for i in range(min(DEPTH, len(root_parts))):
        incident_root = os.path.join(incident_root, root_parts[i]+"\\")
    #print("\rsearching", incident_root,  str(datetime.fromisoformat(ts)),end="")
    return incident_root


def reported_date(match):
    row = match["row"]
    header_to_find = None
    sheet = row["sheet_name"]
    if sheet == "EAA-720":
        header_to_find = "Date"
    if sheet == "LOT-710":
        header_to_find = "Date"
    if sheet == "CRO-345":
        header_to_find = "Occ Date"
    ix = 0
    for h in row["headers"]:
        if h is not None and h.strip() == header_to_find:
            break
        ix += 1
    matched_date = row["row_values"][ix]
    dt = datetime.strptime(matched_date, "%Y-%m-%d %H:%M:%S")
    return dt

def unmatch(match, ts):
    #src_len = len(match.get("matched_source_lines", []))
    #score = match.get("score", 0)
    #if src_len == 0 or src_len > score:
    #    print("skipping", str(datetime.fromisoformat(ts)))
    #    return True# skip, not fully matching
    ts_formated = ts.split("+")[0].replace("T", " ")
    cells = match.get("row",{}).get("row_values",[])
    if cells is None or len(cells) == 0:
        print("\nUnmatching", ts_formated)
        return True
    for val in cells:
        if type(val) is not str:
            continue
        if ts_formated in val:
            return False# definitely this time! :)
    print("\nUnmatching", ts_formated)
    return True

from datetime import timezone
def read_times_file(times_file, root, time_differences, incidents):
    """
    Reads source_date_row_matches_best.json and yields only timestamps
    whose entry has a non-empty 'matches' list.

    The yielded time is the TOP-LEVEL KEY, e.g.:
    '2022-06-01T07:17:53+01:00'
    parsed into a datetime.
    """
    with open(times_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", {})

    for ts, entry in results.items():
        matches = entry.get("matches", [])
        if not matches:
            continue
        match = matches[0]
        if unmatch(match, ts):
            continue
        reported_time = reported_date(match)
        actual_time = datetime.fromisoformat(ts)
        if reported_time.tzinfo is None:
            reported_time = reported_time.replace(tzinfo=timezone.utc)
        if actual_time.tzinfo is None:
            actual_time = actual_time.replace(tzinfo=timezone.utc)
        diff = time_diffs.signed_difference_record(reported_time, actual_time)
        time_differences.append(diff)
        incident_root = get_incident_root(root, match, ts)
        incident_time = actual_time#reported_time
        
        entry["mapped_date"] = reported_time.isoformat()
        incidents[str(ts)]=entry
        
        yield reported_time, incident_time.isoformat(), incident_root, entry


def parse_args():
    parser = argparse.ArgumentParser(
        description="If no --time_file, then --xlsx_file shall help it map incidents from --root. Furthermore performs chunking and can perform anomally detection. Besides that can perform --line_analysis."
    )
    parser.add_argument(
        "-r", "--root",
        dest="root",
        type=str,
        #required=True,
        default=None,
        help="Path to the root folder"
    )
    parser.add_argument(
        "-d", "--dest",
        dest="dest",
        type=str,
        required=True,
        help="Path to the dest folder"
    )
    parser.add_argument(
        "-t", "--time_file",
        dest="time_file",
        type=str,
        #required=True,
        default=None,
        help="Path to the time_file"
    )
    parser.add_argument(
        "-x", "--xlsx_file",
        dest="xlsx_file",
        type=str,
        #required=True,
        default=None,
        help="Path to the incidents file"
    )
    parser.add_argument(
        "-c", "--chunk_max",
        dest="chunk_max",
        type=int,
        #required=True,
        default=1000,
        help="Maximal chunk size in characters"
    )
    
    parser.add_argument(
        "-anom", "--detect-anomalies",
        dest="det_anom",
        action="store_true"
        , help="Detect anomalies"
    )
    
    parser.add_argument(
        "-lanal", "--line_analysis",
        dest="line_analysis",
        action="store_true"
        , help="Perform line analysis"
    )
    
    args = parser.parse_args()
    time_file = args.time_file
    if time_file is None:
        time_file = Matchmaker.api(root=args.root, xlsx_file=args.xlsx_file)#root = "C:\\Datasets\\MonLis\\"
    return args.root, args.dest, time_file, args.det_anom, args.line_analysis, args.chunk_max


def main():
    root, dest, times_file, det_anom, lanal, CHUNK_SIZE = parse_args()
    if root:
        api(root=root, dest=dest, times_file=times_file, CHUNK_SIZE=CHUNK_SIZE, anomally_detection=det_anom)
    else:
        print("No destination specified.")
    if lanal:
        print("Performing line analysis...")
        line_analysis_api(times_file=times_file, dest_root=dest)

SPAN_START = timedelta(days=1)
SPAN_AFTER_END = timedelta(days=1)

def line_analysis_api(times_file, dest_root):
    time_differences = []
    line_lengths = []
    incidents = {}
    import matplotlib as mtl
    font = {#'family' : 'normal',
            #'weight' : 'normal',
            'size'   : 12}
    mtl.rc('font', **font)
    for reported_time, _incident_ts, incident_root, entry in read_times_file(times_file
                                                        , dest_root
                                                        , time_differences
                                                        , incidents):
        time_start = reported_time - SPAN_START
        time_end = reported_time + SPAN_AFTER_END
    
        incidents_line_len = DESAnalyst.line_lens_analysis_api(dest_root
                                                            , ts_mark=_incident_ts
                                                            , time_start=time_start
                                                            , time_end=time_end)
        line_lengths.extend(incidents_line_len)
    line_lengths_hists.plot_line_length_hist_grid(line_lengths=line_lengths
                                                  ,out_path="out/line-lengths-grid.pdf"
                                                  ,show=False)
    for OUTLIER_LIMIT in [500, 1000, 2000, 3000, 4000, 5000, 10000]:
        line_lengths_hists.plot_line_length_hist_with_outlier_bin(line_lengths=line_lengths
                                                              , OUTLIER_LIMIT=OUTLIER_LIMIT
                                                              ,out_path="out/line-lengths-outliers"+str(OUTLIER_LIMIT)+".pdf"
                                                              ,show=False)
    for c in [True, False]:
        line_lengths_hists.plot_line_length_cdf(line_lengths=line_lengths
                                            ,show=False
                                            ,out_path="out/line-lengths-cumulative"+str(c)+".pdf"
                                            ,complementary=c)

def api(root, dest
        , times_file, CHUNK_SIZE, anomally_detection=False
        #, inc_json = 
        , LIMIT_CONTENT=True):
    inc_dst = "out/"+str(CHUNK_SIZE)+"/"
    inc_json = inc_dst+"chunked_incidents.json"
    time_differences = []
    chuns = []
    incidents = {}
    after_dedustats = []
    for reported_time, _incident_ts, incident_root, entry in read_times_file(times_file
                                                        , root
                                                        , time_differences
                                                        , incidents):
        time_start = reported_time - SPAN_START
        time_end = reported_time + SPAN_AFTER_END

        chunk_sizes, anomalies, chunk_dest, after_dedu = DESAnalyst.api(
            incident_root,
            dest,
            time_start,
            time_end,
            ts_mark=_incident_ts
            ,chunk_size=CHUNK_SIZE
            , INCLUDE_STATIC_FILES=True
            , anom_detect=anomally_detection
            , LIMIT_CONTENT=LIMIT_CONTENT
        )
        reduction = 1-after_dedu# 1 - remained
        chuns.extend(chunk_sizes)
        entry["anomalies"] = anomalies
        entry["chunked_destination"]  = chunk_dest
        entry["remained_dedu"] = reduction
        after_dedustats.append(reduction)
        print("\rINCIDENT:",len(incidents), " ", end="")
    import Visualizations.hist as Viz_Hist
    Viz_Hist.hist_from_array(chuns, x="Chunk Size", y="Frequency", title="Chunk Sizes", dest=inc_dst, show=False)
    time_diffs.plot_difference_histograms(time_differences, unit="hours", bins=30, title="Reported vs actual time")
    import json
    #os.makedirs(inc_json, exist_ok=True)
    inc_json = os.path.abspath(inc_json)
    os.makedirs(os.path.dirname(inc_json), exist_ok=True)
    with open(inc_json, "w", encoding="utf-8") as fp:
        json.dump(incidents, fp,
        default=str)
    print("\nFinished, results were written into:", inc_json)
    Viz_Hist.hist_from_array_single(after_dedustats, x="Reduction", y="Frequency", title="Reduction by Deduplication", dest=inc_dst, show=True)
    print("Reduction: ", evaluate_IR.metric_statistics(after_dedustats))
    return inc_json
    
if __name__ == "__main__":
    main()
    


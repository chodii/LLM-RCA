# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 19:29:01 2026

@author: chodo
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import _dataset_walker as walker
import DatasetInspection.path_parser as path_parser
import Window.ExtractorBinary as ExtractorBinary
import Window.ExtractorLog as ExtractorLog


NONE_TYPE = "none"
UNKNOWN_TYPE = "unk"
DATA_KEY="data"
FP_KEY="fp"
FILE_NAME_KEY="file_name"

class DatasetWindow():
    def __init__(self, 
                     file_filters,
                     non_signif_exts,
                     ignore,
                     time_start = None# whole files
                     ,time_end=None
                 ):
        
        self.file_filters   = file_filters
        self.non_signif_exts= non_signif_exts
        self.ignore         =ignore
        self.time_start     =time_start
        self.time_end       =time_end
        
        self.ignored_files  = []
        self.processed_files= 0
        self.NONE_TYPE      = NONE_TYPE
        self.UNKNOWN_TYPE   = UNKNOWN_TYPE
        
    def classify_file_type(self, filename):
        #filename = filename[1:]# ignore first character for e.g. .hmi_runtime.log files
        for ns in self.non_signif_exts:
            filename=filename.replace("."+ns, "")
        for i in self.ignore:
            if i in filename:
                return None
        extentions = filename.split(".")
        if len(extentions) == 0:
            return self.NONE_TYPE
        for ext in extentions:#[1:]:
            if ext in self.file_filters:
                return ext
        return self.UNKNOWN_TYPE
        
    def process(self, current_dir, filename):
        fp = os.path.join(current_dir, filename)
        file_type = self.classify_file_type(filename)
        if file_type is None or file_type not in self.file_filters:# ignored file
            self.ignored_files.append(fp)
            return
        file_processor = self.file_filters[file_type]
        try:
            time_anchor = path_parser.extract_best_anchor_from_path(fp)
        except:
            time_anchor = None
        if self.time_start is None and self.time_end is None:
            res = file_processor(file_path=fp
                                 , time_anchor=time_anchor)
        else:
            res = file_processor(file_path=fp
                             , time_start=self.time_start
                             , time_end=self.time_end
                             , time_anchor=time_anchor)
        return res
        

    
# blahblah06.12.2022
""", "txt":
, "status":
, NONE_TYPE:
, UNKNOWN_TYPE:
, "stderr":"""
from datetime import datetime, timezone, timedelta

def extract_time_relevant_events(root, time_start, time_end, INCLUDE_STATIC_FILES=False, spec_files_only=None, ignore=None):
    ExtractorLog.reset_counter()
    if time_start is None and time_end is None:
        LOG_EXTRACTOR = ExtractorLog.all_from_log
        BIN_EXTRACTOR = ExtractorBinary.all_from_binary
    else:
        LOG_EXTRACTOR = ExtractorLog.window_from_log
        BIN_EXTRACTOR = ExtractorBinary.window_from_binary
        ExtractorLog.INCLUDE_STATIC_FILES = INCLUDE_STATIC_FILES
        
    file_filters={
            "log":LOG_EXTRACTOR#(self, file_path, time_start, time_end)
            , "bin":BIN_EXTRACTOR#(file_path, time_start, time_end)
            , "txt":LOG_EXTRACTOR
            , NONE_TYPE:LOG_EXTRACTOR
            , "status":LOG_EXTRACTOR# log-rotate files, probably useless
            , UNKNOWN_TYPE:LOG_EXTRACTOR
            
            ,"xml":LOG_EXTRACTOR
            ,"js":LOG_EXTRACTOR
            }
    if spec_files_only is not None and type(spec_files_only) == list:
        files_only = {}
        for k in spec_files_only:
            files_only[k] = file_filters[k]
        file_filters = files_only
    if ignore is None:
        ignore = ["pdf", "xlsx", "docx"
                      , "stderr"# they are empty anyway
                      , "swp"# swp is a recovered file, there is one in the dataset, ignored for simplicity
                      , "lastlog"#binary so use :ExtractorBinary.window_from_binary# recent login events
                  ]

    non_signif = ["bkp", "old"]
    for i in range(9):
        non_signif.append(str(i))

    DP = DatasetWindow(
            file_filters     =file_filters
            ,non_signif_exts =non_signif
            , ignore         =ignore
            , time_start     =time_start
            , time_end       = time_end
        )
    for current_dir, filename in walker.dataset_crude_iterator(root):
        print('\r', ExtractorLog.STATISTICS_COUNTER, end="")
        res = DP.process(current_dir, filename)
        if res is None:
            continue
        yield {
            FILE_NAME_KEY:filename
            ,FP_KEY:os.path.join(current_dir, filename)[len(root):]# only the relevant part of the dataset
            , DATA_KEY:res}


    
def extract_subset_plain(root, time_end, time_start, dest="C:\\Datasets\\processed\\monlis_"):
    if time_start is None or time_end is None:
        print("Extracting information from across the all time, structured as JSON.")
    else:
        print("Extracting information from ",time_start.isoformat(),"to", time_end.isoformat(), "structured as JSON")
    reserved_names={}
    
    dest = dest+time_start.isoformat()[:10]+"\\"
    os.makedirs(dest, exist_ok=True)
    for events_log in extract_time_relevant_events(root, time_start, time_end):
        filename = walker.unique_name(events_log[FILE_NAME_KEY], reserved_names)
        dest_file = os.path.join(dest, filename)
        with open(dest_file, "w", encoding="utf-8") as dfp:
            dfp.write(events_log[FP_KEY]+"\n")
            for (time, line) in events_log[DATA_KEY]:
                dfp.write(time.isoformat() +": "+ str(line)+"\n")

import json
from Chunking import chunker
def extract_subset_json(root, time_end, time_start, dest, INCLUDE_STATIC_FILES):
    if time_start is None or time_end is None:
        print("Extracting information from across the all time, structured as JSON.")
    else:
        print("Extracting information from ",time_start.isoformat(),"to", time_end.isoformat(), "structured as JSON")
    reserved_names={}
    
    os.makedirs(dest, exist_ok=True)
    for events_log in extract_time_relevant_events(root, time_start, time_end, INCLUDE_STATIC_FILES):
        filename = events_log[FILE_NAME_KEY].replace(".", "")
        filename = walker.unique_name(filename, reserved_names)
        dest_file = os.path.join(dest, filename)
        data=[]
        for (time, line) in events_log[DATA_KEY]:
            data.append([time.isoformat() if time is not None else None, line])
        FILE_AS_JSON = {
                chunker.KEY_SRC_PTH : events_log[FP_KEY]
                , chunker.KEY_CONTENT : data
            }
        with open(dest_file+".json", "w", encoding="utf-8") as jfp:            
            json.dump(FILE_AS_JSON, jfp)
    #return dest

def main():
    root = "C:\\Datasets\\MonLis\\CRO_NOSS_Example\\"
    #time_end = datetime(2021,11,3,11,25,16,tzinfo=timezone.utc)
    #time_end = datetime(2025,2,6,16,6,0,tzinfo=timezone.utc)
    #time_start = time_end - timedelta(minutes=30)
    
    # ??? not at all within the data set
    #time_end = datetime(2021,11,12,10,22,44,tzinfo=timezone.utc)
    #time_start = datetime(2021,11,8,10,22,44,tzinfo=timezone.utc)
    
    # 600 files, no related issue identified
    #time_end = datetime(2021,12,16,10,21,0,tzinfo=timezone.utc)
    #time_start = time_end - timedelta(minutes=10)
    
    #2025-03-03 11:35:54
    
    #time_end = datetime(2025,1,10,17,0,0,tzinfo=timezone.utc)
    #time_start = datetime(2025,1,20,16,0,0,tzinfo=timezone.utc)
    
    
    for day, hour, minute, second in [  
                  (3, 10, 55, 56)
                , (7, 16, 10, 51)
                , (10,10, 31, 28)
                , (11, 9, 15, 26)]:
        time_end = datetime(2025, 3, day, hour, minute, second, tzinfo=timezone.utc)
        time_end = time_end + timedelta(minutes=10)
        time_start = time_end - timedelta(minutes=60)
        extract_subset_json(root, time_end, time_start)
    
if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 18:48:13 2026

@author: chodo
"""


import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Window import WindowedDataSelection
from Window import hist_yearly
from Window import hist_monthly

from datetime import datetime, timezone, timedelta
years = None

def gather_data_for_plot(spec_files_only, incl_stat_f):
    
    root = "C:\\Datasets\\MonLis"
    time_start = datetime(1900,3,10,21,40,16,tzinfo=timezone.utc)
    time_end = datetime(2026,4,14,21,40,16,tzinfo=timezone.utc)
    years = {}
    for events_log in WindowedDataSelection.extract_time_relevant_events(root, time_start, time_end
                                                                         , INCLUDE_STATIC_FILES=incl_stat_f
                                                                         , spec_files_only=spec_files_only):
        for (time, line) in events_log[WindowedDataSelection.DATA_KEY]:
            #n+=1
            if time is not None:
                year = time.isoformat()[:4]
            else:
                year="1970"
            if year not in years:
                years[year] = {}
            if time is not None:
                month = time.isoformat()[5:7]
            else:
                month="1"
            if month not in years[year]:
                years[year][month] = 0
            years[year][month] += 1
    return years

def main():
    global years
    import matplotlib as mtl
    font = {#'family' : 'normal',
            #'weight' : 'normal',
            'size'   : 10}
    mtl.rc('font', **font)
    import json
    spec_files_only = [["log", "bin", "txt", "status", "xml", "js", WindowedDataSelection.NONE_TYPE, WindowedDataSelection.UNKNOWN_TYPE]]#["txt"], ["log"], [WindowedDataSelection.NONE_TYPE, WindowedDataSelection.UNKNOWN_TYPE], None]
    ignore_all = ["pdf", "xlsx", "docx", "stderr", "swp", "lastlog"
              , "log", "bin", "txt", "status", "xml", "js", WindowedDataSelection.NONE_TYPE, WindowedDataSelection.UNKNOWN_TYPE]
    incl_stat_f = [True, False]
    for files in spec_files_only:
        ignore = []
        if ignore_all:
            for f in ignore_all:
                if f not in files:
                    ignore.append(f)
        else:
            ignore = None
        for stat_f in incl_stat_f:
            if files is not None:
                tag = " "+files[0]
            else:
                tag = " all"
            tag = " for all considered file formats"
            if not stat_f:
                tag += " excluding static files"
            else:
                tag += " including static files"
            print("\n",tag)
            years = gather_data_for_plot(spec_files_only=files, incl_stat_f=stat_f)
            if len(years) == 0:
                continue
            hist_yearly.plot_data(years, tag=tag, show=False)
            hist_monthly.plot_data(years, tag=tag, show=False)
    #with open("years.json", "w") as fp:
    #    json.dump({"years":years, "stats":WindowedDataSelection.ExtractorLog.STATISTICS_COUNTER}, fp)

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 10:10:18 2026

@author: chodo
"""

import json
import os
TEXT_KEY="text"
def main():
    fp_id="watchdog"
    file_name="events"+fp_id+".json"
    with open(file_name, "r") as fp:
        log = json.load(fp)
        unique_texts=set()
        for timestamp in log:
            file_events = log[timestamp]
            if type(file_events) is not list:
                file_events = [file_events]
            for eve in file_events:
                txt = eve[TEXT_KEY]
                if len(txt) > 1:
                    print(len(txt))
                unique_texts.add(txt[0])
    for t in unique_texts:
        print(t)

if __name__=="__main__":
    main()
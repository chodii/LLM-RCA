# -*- coding: utf-8 -*-
"""
Created on Wed Feb 18 16:03:53 2026

@author: chodo
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import argparse
import json
from pathlib import Path

from DatasetInspection import time_parser
from DatasetInspection import path_parser

def looks_binary(path: Path, sniff_bytes: int = 4096) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(sniff_bytes)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        # crude heuristic: many control chars => likely binary
        nontext = sum(1 for b in chunk if b < 9 or (13 < b < 32) or b == 127)
        return (nontext / len(chunk)) > 0.20
    except Exception:
        # If we can't read it safely, treat as binary/unprocessable
        return True

class DataPreprocessor():
    def __init__(self):
        self.skipped_files = []
        self.processed_files = 0
        self.times = {}
        self.years = {}
        
    def dataset_iterator(self, root: Path, skip_binary=True):
        for current_dir, subdirs, files in os.walk(root):
            for filename in files:
                fp = os.path.join(current_dir, filename)
                if skip_binary and looks_binary(fp):
                    self.skipped_files.append(fp)
                    continue
                yield fp
            
    def log_time(self, time, proctid):
        if time is None:
            return
        if proctid not in self.times:
            self.times[proctid] = {"min":time, "max":time, "count":1}
            return
        if time < self.times[proctid]["min"]:
            self.times[proctid]["min"] = time
        if time > self.times[proctid]["max"]:
            self.times[proctid]["max"] = time
        self.times[proctid]["count"] += 1
        year = str(time)[:4]
        if year not in self.years:
            self.years[year] = 1
            return
        self.years[year] += 1
    
    def process(self, root, encoding="utf-8"):
        for fp in self.dataset_iterator(root):
            try:
                if ".log" not in fp:
                    self.skipped_files.append(fp)
                    continue
                with open(fp, "r", encoding=encoding) as f:
                    self.processed_files += 1
                    
                    time_anchor = path_parser.extract_best_anchor_from_path(fp or "")
                    for line_no, raw_line in enumerate(f, start=1):
                        proc_line, time, proctid = time_parser.normalize_line_extract_time(raw_line, time_anchor)
                        self.log_time(time.isoformat(), proctid)
                print("processed:", self.processed_files,"-------", end="\r")
            except Exception:
                print("ERROR", fp)
                self.skipped_files.append(fp)
        print("All done!")
        print(self.processed_files," processed; skipped:",len(self.skipped_files))
        print("Times:")
        print(self.times)
        print("Years:\n", self.years)

if __name__ == "__main__":
    proc = DataPreprocessor()
    proc.process("C:\\Datasets\\DESu\\")
    
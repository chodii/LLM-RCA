# -*- coding: utf-8 -*-
"""
Created on Mon Mar  9 03:20:02 2026

@author: chodo
"""

import os

SEARCH_SUBSTRING = "EMERGENCY:MPSPThreads::Restart"   # change this to what you want to search for
ROOT_DIR = "C:\\Datasets\\MonLis\\"                    # directory to scan
LOG_FILE = "matches_EMERGENCY-MPSPThreads-Restart.log"


def is_binary(file_path):
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return True
    except Exception:
        return True
    return False


def scan_files():
    print("sniffing in ", ROOT_DIR)
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        for root, dirs, files in os.walk(ROOT_DIR):
            for file in files:
                path = os.path.join(root, file)

                if is_binary(path):
                    continue
                found = False
                found_id = 0
                try:
                    entry = ""
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, start=1):
                            if found:
                                if found_id < 10:
                                    found_id += 1
                                    entry += "\n"+line
                                else:
                                    found_id = 0
                                    found = False
                                    log.write(entry)
                            if SEARCH_SUBSTRING in line:
                                entry = f"\n{path}:\n{i}: {line}"
                                found = True
                    if found:
                        log.write(entry)
                except Exception:
                    pass

import sys
if __name__ == "__main__":
    if len(sys.argv) > 1:
        ROOT_DIR = sys.argv[1]
    scan_files()
    print(f"Scan complete. Results saved to {LOG_FILE}")
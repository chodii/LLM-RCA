# -*- coding: utf-8 -*-

"""

Created on Wed Apr 22 18:31:10 2026



@author: chodo

"""



import os

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Database import db_loader



from DataPreprocessing.Window import ExtractorLog



import json

DEST_KEY = "chunked_destination"

TS_KEY = "mapped_date"

ROW_KEY = "row"

HEADER_KEY = "headers"

ROW_VALS_KEY = "row_values"

SHEET_KEY = "sheet_name"

MATCHES_KEY = "matches"



DESCRIPTION = "description"

TARGET = "target"

ISSUE = "issue"

SHEET_MAP = {

    "EAA-720":{DESCRIPTION:"details +time"

               , TARGET:"Developer's analysis"

               , ISSUE:"Type of NOSS"}

    ,"LOT-710":{DESCRIPTION:"Details and time"

                , TARGET:"TCMS HMI team analysis"

                , ISSUE:"Type of NOSS"}

    ,"CRO-345":{DESCRIPTION:"Details and time"

                , TARGET:"Comments from Developer"

                , ISSUE:"Issue TYPE"}

    }



def load_incidents(incidents_json, chunk_size, OUT, ignore_cov_file = False):#="out/chunked_"

    incidents = None

    with open(incidents_json, "r", encoding="utf-8") as fp:

        incidents = json.load(fp)

    relevant_chunks = {}

    cov_file = OUT+"/coverage_analysis.json"

    if os.path.exists(cov_file) and not ignore_cov_file:

        with open(cov_file, "r", encoding="utf-8") as fp:

            cover_anal = json.load(fp)

            for i, ts in enumerate(cover_anal["files"]):

                relevant_chunks[ts] = {"files":cover_anal["files"][ts]

                                       , "score":{k:cover_anal["coverage"][k][i] for k in cover_anal["coverage"]}

                                       , "files_all":cover_anal["files_all"][ts]}

    for k in incidents:

        incident = Incident(incident=incidents[k])

        incident.set_relevant_chunks(relevant_chunks.get(incident.ts, None))

        yield incident



def extract_from_sheet(row, information):

    ix = 0

    sheet = row[SHEET_KEY]

    header_to_find = SHEET_MAP[sheet][information]

    found=False

    for h in row[HEADER_KEY]:

        if h is not None and h.strip() == header_to_find:

            found=True

            break

        ix += 1

    if not found:

        print("SHOULD FIND", ">"+header_to_find+"<")

    matched_val = row[ROW_VALS_KEY][ix]

    return matched_val



def load_target_chunk_info(target_files, _target_chunks):

    for file in target_files:

        with open(file, mode="r", encoding="utf-8") as fp:

            content = json.load(fp)

            src = {"source_path":content["source"], "chunk_id":content.get("chunk_id", None)}

            _target_chunks.append(src)



def rec_to_txt(l):

    ts = l[0]

    content = l[-1]

    if ts:

        if len(l) == 2:

            if type(ts) == list:

                print(str(l))

                return None

            line = str(ts if type(ts) == str else ts.isoformat())+" "+str(content)

        else:

            line = str(l[2])+" times between "+(l[0] if type(l[0]) == str else l[0].isoformat())+" and "+(l[1] if type(l[1]) == str else l[1].isoformat())+" "+l[-1]

    else:

        line = str(content)

    return line





class Incident:

    def __init__(self, incident):

        self.chunk_folder = incident[DEST_KEY]

        self.ts = incident[TS_KEY]

        match = incident[MATCHES_KEY][0]

        row = match[ROW_KEY]

        self.description = extract_from_sheet(row, DESCRIPTION)

        self.raw_target = extract_from_sheet(row, TARGET)

        self._target=None

        self.issue_type = extract_from_sheet(row, ISSUE)

        self._target_chunks_unique = None

        self._target_chunks_all = None

        self._target_score = None

        self.target_times = []# not used yet



    

    def __str__(self):

        return str(self.chunk_folder) + "\t" + str(self.ts)

    

    def get_target(self):

        if not self._target:

            converted_target = ExtractorLog.all_from_text(self.raw_target)

            preprocessed = []

            for line in converted_target:

                self.target_times.append(line[0])

                preprocessed.append(line[-1])

            self._target = ""

            for i in range(len(preprocessed)-1):

                self._target+=preprocessed[i]+"\n"

            self._target += preprocessed[-1]

        return self._target

    

    def swap_into_db(self):

        db_loader.api(root=self.chunk_folder)



    def set_relevant_chunks(self, rel_chunks):

        if rel_chunks is None:

            return

        target_files_unique = rel_chunks["files"]

        self._target_chunks_unique = []

        self._target_score = rel_chunks["score"]

        load_target_chunk_info(target_files_unique, self._target_chunks_unique)

        

        target_files_all = rel_chunks["files_all"]

        self._target_chunks_all = []

        load_target_chunk_info(target_files_all, self._target_chunks_all)

    

    def get_relevant_chunks(self):

        return self._target_chunks_unique, self._target_chunks_all

    

    def get_potential_scores(self):

        return self._target_score

        



def log_file_reader(pth):

    content = None

    with open(pth, "r", encoding="utf-8") as fp:

        file = json.load(fp)

        content = file["content"]

    #if len(content) >= 1 and ((len(content[0]) == 2 and type(content[0][1])==dict) or (type(content[0][0])==dict)):

    #    print("\ndict:",pth)

    for line in line_in_content(content, pth):

        yield line



def line_in_content(content, pth=None):

    for log_entry in content:

        if len(log_entry) >= 2:

            cont = ""

            if type(log_entry[-1]) == dict:

                for k in log_entry[-1]:

                    cont += str(log_entry[-1][k])+" "

            elif type(log_entry[-1]) == str:

                cont = log_entry[-1]

            else:

                raise Exception(str(type(log_entry[1]))+" type in log_entry[1] for: "+pth)

        for line in cont.split("\n"):

            yield line
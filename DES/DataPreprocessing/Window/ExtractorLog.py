# -*- coding: utf-8 -*-

"""

Created on Wed Mar  4 23:28:43 2026



@author: chodo

"""

import os

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import DatasetInspection.time_parser as TP

import DatasetInspection.path_parser as PP



INCLUDE_STATIC_FILES=True



STATISTICS_COUNTER = None



def reset_counter():

    global STATISTICS_COUNTER

    STATISTICS_COUNTER = {"files":0

                        ,"extracted":0

                        , "missed":0

                        ,"ERROR":0}

        

def all_from_line(raw_line, res, time_anchor, ext_time):

    raw_line = raw_line.strip()

    if len(raw_line) == 0:

        return ext_time# empty line

    proc_line, time, proctid = TP.normalize_line_extract_time(raw_line, time_anchor)

    if time is not None:

        ext_time=time

        res.append([time, proc_line])

        return ext_time

    if ext_time is None:

        if time_anchor is not None:

            res.append([time_anchor.dt, proc_line])

            return ext_time

        if INCLUDE_STATIC_FILES:

            res.append([None, proc_line])# static part of a file

    # there is some previous event this belongs to

    res[-1][1] = res[-1][1] +"\n"+proc_line

    return ext_time



def all_from_log(file_path, time_anchor=None, encoding="utf-8"):

    res = []

    ext_time = None

    time_extr_issue = 0

    with open(file_path, "r", encoding=encoding) as f:

        time_anchor = PP.extract_best_anchor_from_path(file_path or "")

        try:

            for line_no, raw_line in enumerate(f, start=1):

                ext_time = all_from_line(raw_line, res, time_anchor, ext_time)

        except Exception as e:

            if STATISTICS_COUNTER is not None:

                STATISTICS_COUNTER["ERROR"]+=1

            else:

                print("ERROR:\t",e, file_path,"\n")

    if STATISTICS_COUNTER is not None:

        STATISTICS_COUNTER["files"] += 1

        STATISTICS_COUNTER["extracted"]+=len(res)

        STATISTICS_COUNTER["missed"]+=time_extr_issue

    else:

        if time_extr_issue != 0:

            print("Time extracting issue occured in file",file_path, "\nlines which failed to be extracted:",time_extr_issue, "\nlines extracted:",len(res),"\n")

    if len(res) == 0:

        return None

    return res



def window_from_log(file_path, time_start, time_end, time_anchor=None, encoding="utf-8"):

    """

    -------

    res : list((time,line))

        list of time-line pairs.



    """

    res = []

    ext_time = None

    PREV_TIME_WRONG = False

    time_extr_issue = 0

    with open(file_path, "r", encoding=encoding) as f:

        try:

            time_anchor = PP.extract_best_anchor_from_path(file_path or "")

        except:

            time_anchor = None

        try:

            for line_no, raw_line in enumerate(f, start=1):

                raw_line = raw_line.strip()

                if len(raw_line) == 0:

                    continue# empty line

                proc_line, time, proctid = TP.normalize_line_extract_time(raw_line, time_anchor)

                if time is not None:

                    if time < time_start or time > time_end:

                        PREV_TIME_WRONG = True

                        continue

                    PREV_TIME_WRONG = False

                    ext_time=time

                    res.append([time, proc_line])

                    continue

                if PREV_TIME_WRONG:

                    continue# the raw_line belongs to a wrong time

                # time is None

                if ext_time is None:

                    if time_anchor is None:

                        #print(proc_line,"\n\n")

                        if INCLUDE_STATIC_FILES:

                            res.append([None, proc_line])

                        else:

                            time_extr_issue += 1# and log the issue

                        continue

                    if time_anchor.dt < time_start or time_anchor.dt > time_end:

                        continue

                    if len(res) == 0:

                        res.append([time_anchor.dt, proc_line])

                        continue

                    res[-1][1] = res[-1][1]+"\n"+proc_line

                    continue

                # there is some previous event this belongs to

                res[-1][1] = res[-1][1] +"\n"+proc_line

                continue

                # it already had the opportunity to extract the anchor

                #if time_anchor is not None:

                #    res.append((time_anchor, proc_line))

                #    continue

                # time is NONE

                # ignore the content

        except Exception as e:

            if STATISTICS_COUNTER is not None:

                STATISTICS_COUNTER["ERROR"]+=1

            else:

                print("ERROR:\t",e, file_path,"\n")

    if STATISTICS_COUNTER is not None:

        STATISTICS_COUNTER["files"] += 1

        STATISTICS_COUNTER["extracted"]+=len(res)

        STATISTICS_COUNTER["missed"]+=time_extr_issue

    else:

        if time_extr_issue != 0:

            print("Time extracting issue occured in file",file_path, "\nlines which failed to be extracted:",time_extr_issue, "\nlines extracted:",len(res),"\n")

    if len(res) == 0:

        return None

    return res



def all_from_text(text:str):

    """

    Extracts log lines from @param text. 



    Parameters

    ----------

    text : TYPE

        DESCRIPTION.



    Returns extracted log-lines [time_ISO, <time> line]

    -------

    res : TYPE

        DESCRIPTION.



    """

    res = []

    ext_time = None

    time_anchor=None

    for raw_line in text.split("\n"):

        ext_time = all_from_line(raw_line, res, time_anchor, ext_time)

    return res




# -*- coding: utf-8 -*-

"""

Created on Sun Mar  8 21:50:46 2026



@author: chodo

"""





import os

import sys






from rca.data_preprocessing.timestamps_incidents import WindowedDataSelection



from datetime import datetime, timezone, timedelta

import json

from collections import Counter, defaultdict



def find_events(text

                ,root#"CRO_NOSS_Example\\"

                ):

    # ^ the only parameter

    

    time_end = datetime(2026,4,3,11,45,0,tzinfo=timezone.utc)

    time_start = datetime(2000,1,1,11,45,0,tzinfo=timezone.utc)

    events = {}

    dates = []

    for events_log in WindowedDataSelection.extract_time_relevant_events(root, time_start, time_end):

        

        for (time, line) in events_log[WindowedDataSelection.DATA_KEY]:

            if text in line:

                dates.append(time)# needs time.isoformat() to print

                strtime= time.isoformat()

                if strtime not in events:

                    events[strtime] = []

                events[strtime].append(

                    {

                        "path":os.path.join(root, events_log[WindowedDataSelection.FP_KEY])

                        ,"text":[l for l in str(line).split("\n")]}

                    )

    return dates, events


import sys
def main():

    root = "C:\\Datasets\\dataset\\"
    if len(sys.argv) >= 2:
        root = sys.argv[1]
    print("Searching in ", root)
    api(root)



def api(root):

    #text="watchdog"

    json_id="-EMERGENCY-MPSPThreads-Restart"

    text="EMERGENCY:MPSPThreads::Restart"

    #text="External watchdog timeout"

    dates, events = find_events(text, root=root)

    # 1) Order dates and print them

    dates.sort()



    print("\n=== Matching event timestamps ===")

    for dt in dates:

        print(dt.isoformat())

    

    # 2) Show distribution of dates

    year_counts = Counter(dt.year for dt in dates)

    month_counts = Counter(dt.strftime("%Y-%m") for dt in dates)

    day_counts = Counter(dt.strftime("%Y-%m-%d") for dt in dates)

    print("\n=== Distribution by year ===")

    for year in sorted(year_counts):

        print(f"{year}: {year_counts[year]}")



    print("\n=== Distribution by month ===")

    for month in sorted(month_counts):

        print(f"{month}: {month_counts[month]}")



    print("\n=== Distribution by day ===")

    for day in sorted(day_counts):

        print(f"{day}: {day_counts[day]}")



    # 3) Write events as JSON file

    # sort by timestamp before saving

    sorted_events = dict(sorted(events.items()))

    os.makedirs("out", exist_ok=True)

    out_file="out/events"+json_id+".json"

    with open(out_file, "w", encoding="utf-8") as f:

        json.dump(sorted_events, f, indent=2, ensure_ascii=False)

    out_file = os.path.abspath(out_file)

    print(f"\nSaved {len(sorted_events)} timestamps to ",out_file)

    print(f"Total matching lines: {sum(len(v) for v in sorted_events.values())}")

    return out_file



if __name__ == "__main__":

    main()
# -*- coding: utf-8 -*-

"""

Created on Tue Feb 24 19:46:21 2026



@author: chodo

"""



import struct, json

from collections import Counter

pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"



PATH=pth+"TPWSFPGALog.bin"

START=11

REC=32



event = Counter()

flags = Counter()

mod   = Counter()



min_s = None

max_s = None

wraps = 0

prev_s = None



with open(PATH,"rb") as f:

    f.seek(START)

    while True:

        rec = f.read(REC)

        if len(rec) < REC:

            break

        sec = struct.unpack(">I", rec[0:4])[0]

        eid = struct.unpack("<H", rec[5:7])[0]

        mcl = struct.unpack("<H", rec[7:9])[0]

        flg = struct.unpack("<H", rec[9:11])[0]



        event[eid] += 1

        mod[mcl] += 1

        flags[flg] += 1



        if min_s is None or sec < min_s: min_s = sec

        if max_s is None or sec > max_s: max_s = sec

        if prev_s is not None and sec < prev_s: wraps += 1

        prev_s = sec



out = {

  "file": PATH,

  "record_size": REC,

  "records": sum(event.values()),

  "wraps": wraps,

  "min_sec": min_s,

  "max_sec": max_s,

  "top_event_ids": event.most_common(30),

  "top_modules": mod.most_common(20),

  "top_flags": flags.most_common(20),

}



with open("TPWSFPGALog_summary.json","w") as w:

    json.dump(out, w, indent=2)



print("wrote TPWSFPGALog_summary.json")
# -*- coding: utf-8 -*-

"""

Created on Tue Feb 24 20:02:09 2026



@author: chodo

"""



import struct, json

from collections import Counter

from datetime import datetime, timezone



pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"

PATH=pth+"TPWSFPGALog.bin"

START = 11

REC = 32



# Timestamp sanity window (adjust if needed)

MIN_OK = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())

MAX_OK = int(datetime(2026, 12, 31, tzinfo=timezone.utc).timestamp())

BAD_SENTINELS = {0xFFFFFFFF, 0x00000000}



def read_record(f, idx):

    f.seek(START + idx * REC)

    return f.read(REC)



def sec_from(rec):

    return struct.unpack(">I", rec[0:4])[0]



def fields_from(rec):

    # Based on what we already observed

    eid = struct.unpack("<H", rec[5:7])[0]

    mcl = struct.unpack("<H", rec[7:9])[0]

    flg = struct.unpack("<H", rec[9:11])[0]

    arg1 = struct.unpack("<I", rec[16:20])[0]

    return eid, mcl, flg, arg1



with open(PATH, "rb") as f:

    f.seek(0, 2)

    file_size = f.tell()

    total = (file_size - START) // REC



    # Find wrap point = first index after a decrease in sec

    prev = None

    wrap_idx = None

    min_s = None

    max_s = None



    for i in range(total):

        rec = read_record(f, i)

        if len(rec) < REC:

            break

        sec = sec_from(rec)

        if prev is not None and sec < prev and wrap_idx is None:

            wrap_idx = i

        prev = sec

        min_s = sec if min_s is None else min(min_s, sec)

        max_s = sec if max_s is None else max(max_s, sec)



    if wrap_idx is None:

        wrap_idx = 0



    # Now iterate in "chronological" ring order: wrap..end, 0..wrap-1

    event = Counter()

    mods = Counter()

    flags = Counter()

    arg1s = Counter()



    kept = 0

    bad_ts = 0



    def accept(sec: int) -> bool:

        if sec in BAD_SENTINELS:

            return False

        return MIN_OK <= sec <= MAX_OK



    order = list(range(wrap_idx, total)) + list(range(0, wrap_idx))



    for i in order:

        rec = read_record(f, i)

        if len(rec) < REC:

            continue

        sec = sec_from(rec)

        if not accept(sec):

            bad_ts += 1

            continue

        eid, mcl, flg, arg1 = fields_from(rec)

        event[eid] += 1

        mods[mcl] += 1

        flags[flg] += 1

        arg1s[arg1] += 1

        kept += 1



out = {

    "file": PATH,

    "file_size": file_size,

    "record_size": REC,

    "total_records": total,

    "wrap_index": wrap_idx,

    "min_sec_raw": min_s,

    "max_sec_raw": max_s,

    "kept_records": kept,

    "discarded_bad_timestamp": bad_ts,

    "top_event_ids": event.most_common(50),

    "top_modules": mods.most_common(30),

    "top_flags": flags.most_common(30),

    "top_arg1": arg1s.most_common(30),

}



with open("TPWSFPGALog_features.json", "w") as w:

    json.dump(out, w, indent=2)



print("wrap_index:", wrap_idx)

print("kept:", kept, "bad_ts:", bad_ts)

print("wrote TPWSFPGALog_features.json")
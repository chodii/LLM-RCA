# -*- coding: utf-8 -*-

"""

Created on Tue Feb 24 19:20:51 2026



@author: chodo

"""



import struct

pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"

import struct

from collections import Counter

from datetime import datetime, timezone



PATH = pth+"TPWSFPGALog.bin"



def find_data_start(data: bytes) -> int:

    # skip long runs of 0x0a or 0x00 at the start

    i = 0

    while i < len(data) and data[i] in (0x0A, 0x00):

        i += 1

    return i



def score_record_size(data: bytes, start: int, nrecs: int, r: int) -> float:

    # Score: for each byte position within the record, measure how "stable" it is.

    # Structured records usually have some stable positions (type/version/flags),

    # whereas wrong alignment looks more random.

    sample = data[start : start + nrecs * r]

    if len(sample) < nrecs * r:

        return -1.0



    stability = 0.0

    for pos in range(r):

        col = sample[pos::r]

        c = Counter(col)

        most = c.most_common(1)[0][1]

        # stability fraction for this byte position

        stability += most / len(col)



    # normalize by record size

    return stability / r



def try_ts_fields(rec: bytes):

    # Try a few plausible timestamp decodings from the *front* of the record.

    out = {}



    # 4-byte BE as unix seconds (common in network/embedded logs)

    be4 = int.from_bytes(rec[0:4], "big")

    if 946684800 <= be4 <= 1893456000:  # 2000..2030-ish

        out["ts_be32_unix"] = datetime.fromtimestamp(be4, tz=timezone.utc).isoformat()



    # 4-byte LE as unix seconds

    le4 = int.from_bytes(rec[0:4], "little")

    if 946684800 <= le4 <= 1893456000:

        out["ts_le32_unix"] = datetime.fromtimestamp(le4, tz=timezone.utc).isoformat()



    # 4-byte LE as milliseconds since boot (show hours)

    out["t_le32_ms"] = f"{le4/1000/3600:.2f} hours"



    # 8-byte BE/LE as counters (just show raw)

    out["raw_be64"] = int.from_bytes(rec[0:8], "big")

    out["raw_le64"] = int.from_bytes(rec[0:8], "little")



    return out



with open(PATH, "rb") as f:

    data = f.read()



start = find_data_start(data)

print("file bytes:", len(data))

print("data start offset:", start, "first bytes:", data[start:start+16].hex())



# Find best record size

best = []

for r in range(16, 65):

    s = score_record_size(data, start, nrecs=400, r=r)

    best.append((s, r))

best.sort(reverse=True)



print("\nTop candidate record sizes:")

for s, r in best[:10]:

    print(f"  r={r:2d} score={s:.4f}")



# Use the top candidate

_, r = best[0]

print("\nUsing record size:", r)



# Print a few records

n = 8

print("\nFirst records (hex):")

for i in range(n):

    rec = data[start + i*r : start + (i+1)*r]

    print(i, rec.hex())



# Try to interpret fields for first few records

print("\nTimestamp interpretation attempts:")

for i in range(min(n, 5)):

    rec = data[start + i*r : start + (i+1)*r]

    print("rec", i, try_ts_fields(rec))



# Also show a simple structured unpack guess if r>=32

if r >= 32:

    print("\nUnpack guess (<IHHHHIII) from first 28 bytes (if it fits):")

    fmt = "<IHHHHIII"  # 4 + 2+2+2+2 + 4+4+4 = 28 bytes

    for i in range(min(n, 5)):

        rec = data[start + i*r : start + (i+1)*r]

        fields = struct.unpack_from(fmt, rec, 0)

        print("rec", i, fields)

        





import struct



with open(PATH,"rb") as f:

    f.seek(11)

    chunk = f.read(32*2000)



secs = [struct.unpack(">I", chunk[i:i+4])[0] for i in range(0,len(chunk),32)]

print("min:", min(secs), "max:", max(secs), "span_s:", max(secs)-min(secs))

print("min date:", datetime.fromtimestamp(min(secs), tz=timezone.utc))

print("max date:", datetime.fromtimestamp(max(secs), tz=timezone.utc))

print("unique seconds in first 2000 recs:", len(set(secs)))
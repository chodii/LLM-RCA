# -*- coding: utf-8 -*-
"""
Created on Tue Feb 24 19:55:53 2026

@author: chodo
"""

import struct
from datetime import datetime, timezone
pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"
PATH=pth+"TPWSFPGALog.bin"
START=11
REC=32

min_s = None
max_s = None
count = 0

with open(PATH,"rb") as f:
    f.seek(START)
    while True:
        rec = f.read(REC)
        if len(rec) < REC:
            break
        sec = struct.unpack(">I", rec[0:4])[0]
        min_s = sec if min_s is None else min(min_s, sec)
        max_s = sec if max_s is None else max(max_s, sec)
        count += 1

print("records:", count)
print("span_s:", max_s-min_s)
print("min:", datetime.fromtimestamp(min_s, tz=timezone.utc))
print("max:", datetime.fromtimestamp(max_s, tz=timezone.utc))
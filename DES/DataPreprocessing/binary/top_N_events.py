# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 15:19:52 2026

@author: chodo
"""

from collections import Counter
import struct

pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"
PATH=pth+"TPWSFPGALog.bin"; START=11; REC=32#; W=192512

START=11
REC=32

event_ids = Counter()

with open(PATH,"rb") as f:
    f.seek(0,2)
    total=(f.tell()-START)//REC

    for i in range(total):
        f.seek(START+i*REC)
        rec=f.read(REC)
        if len(rec)<REC:
            break

        ts = struct.unpack(">I",rec[0:4])[0]
        if ts in (0,0xffffffff):
            continue

        eid = struct.unpack("<H",rec[5:7])[0]
        event_ids[eid]+=1

print("Top event IDs:")
for eid,cnt in event_ids.most_common(10):
    print(eid,cnt)
# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 14:46:55 2026

@author: chodo
"""


pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"
PATH=pth+"TPWSFPGALog.bin"; START=11; REC=32#; W=192512
import struct
from datetime import datetime, timezone

START=11
REC=32

WINDOW_MINUTES=30

events=[]

with open(PATH,"rb") as f:
    f.seek(0,2)
    total=(f.tell()-START)//REC

    for i in range(total):
        f.seek(START+i*REC)
        rec=f.read(REC)
        if len(rec)<REC:
            break

        ts=struct.unpack(">I",rec[0:4])[0]
        if ts in (0,0xffffffff):
            continue

        eid=struct.unpack("<H",rec[5:7])[0]
        mod=struct.unpack("<H",rec[7:9])[0]
        flg=struct.unpack("<H",rec[9:11])[0]

        events.append((ts,eid,mod,flg))

# find end time
end_ts=max(e[0] for e in events)

start_window=end_ts-WINDOW_MINUTES*60

print("Window:",datetime.fromtimestamp(start_window,timezone.utc),
      "->",datetime.fromtimestamp(end_ts,timezone.utc))

for ts,eid,mod,flg in events:
    if ts>=start_window:
        print(datetime.fromtimestamp(ts,timezone.utc),eid,mod,flg)
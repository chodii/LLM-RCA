# -*- coding: utf-8 -*-

"""

Created on Tue Feb 24 19:55:22 2026



@author: chodo

"""



import struct

from collections import Counter

pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"



PATH=pth+"TPWSFPGALog.bin"

START=11

REC=32



deltas = Counter()

prev = None

samples = 20000



with open(PATH,"rb") as f:

    f.seek(START)

    for i in range(samples):

        rec = f.read(REC)

        if len(rec) < REC:

            break

        tail = struct.unpack("<H", rec[30:32])[0]

        if prev is not None:

            deltas[(tail - prev) & 0xFFFF] += 1

        prev = tail



print("Most common deltas between last2bytes:")

for d,c in deltas.most_common(10):

    print(d, c)
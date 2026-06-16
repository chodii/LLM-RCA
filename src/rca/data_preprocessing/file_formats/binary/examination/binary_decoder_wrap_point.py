# -*- coding: utf-8 -*-

"""

Created on Tue Feb 24 19:51:33 2026



@author: chodo

"""



import struct

pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"



PATH=pth+"TPWSFPGALog.bin"

START=11

REC=32



wraps = 0

first_wrap_at = None

prev = None



with open(PATH,"rb") as f:

    f.seek(START)

    i = 0

    while True:

        rec = f.read(REC)

        if len(rec) < REC:

            break

        sec = struct.unpack(">I", rec[0:4])[0]

        if prev is not None and sec < prev:

            wraps += 1

            if first_wrap_at is None:

                first_wrap_at = i

        prev = sec

        i += 1



print("records:", i, "wraps:", wraps, "first_wrap_record_index:", first_wrap_at)
# -*- coding: utf-8 -*-

"""

Created on Tue Feb 24 20:10:39 2026



@author: chodo

"""



import struct

from datetime import datetime, timezone



pth = "C:/Datasets/DESu/IssueClosed/CRO_NOSS_Example/503223743_u974c5760/T56 HMI  DMI 10.3.25/UIC345056_2025-03-10_21_41_05_u1881acea/UIC345056_Cab1_TPWS_2025-03-10T21_41_04_u5ff64a0e/"

PATH=pth+"TPWSFPGALog.bin"; START=11; REC=32; W=192512



def ts_at(idx):

    with open(PATH,"rb") as f:

        f.seek(START + idx*REC)

        rec = f.read(REC)

    sec = struct.unpack(">I", rec[0:4])[0]

    return sec, datetime.fromtimestamp(sec, tz=timezone.utc)



for i in range(W-3, W+3):

    sec, dt = ts_at(i)

    print(i, sec, dt)





# timestamp_counting

bad = 0; total = 0



with open(PATH,"rb") as f:

    f.seek(0,2)

    total = (f.tell()-START)//REC

    for i in range(total):

        f.seek(START+i*REC)

        rec = f.read(REC)

        if len(rec) < REC: break

        sec = struct.unpack(">I", rec[0:4])[0]

        if sec == 0xFFFFFFFF:

            bad += 1



print("total", total, "ffffffff", bad, "percent", 100*bad/total)
# -*- coding: utf-8 -*-

"""

Created on Wed Mar  4 23:21:50 2026



@author: chodo

"""



import struct

from datetime import datetime, timezone

def all_from_binary(file_path, time_anchor=None):

    START = 11

    REC = 32

    INVALID = {0xFFFFFFFF, 0}

    

    events = []



    with open(file_path, "rb") as f:



        f.seek(0, 2)

        total_records = (f.tell() - START) // REC



        for i in range(total_records):



            f.seek(START + i * REC)

            rec = f.read(REC)



            if len(rec) < REC:

                break



            # timestamp (big endian)

            ts = struct.unpack(">I", rec[0:4])[0]



            if ts in INVALID:

                continue

            

            time = datetime.fromtimestamp(ts, timezone.utc)

            event = {

                "timestamp": time.isoformat().replace("+00:00", "Z"),

                "event_id": struct.unpack("<H", rec[5:7])[0],

                "module": struct.unpack("<H", rec[7:9])[0],

                "flags": struct.unpack("<H", rec[9:11])[0],

                "subcode": struct.unpack("<H", rec[11:13])[0],

                "arg1": f"0x{struct.unpack('<I', rec[16:20])[0]:08x}",

                "arg2": f"0x{struct.unpack('<I', rec[20:24])[0]:08x}",

                "arg3": f"0x{struct.unpack('<I', rec[26:30])[0]:08x}",

            }



            events.append((time, event))

    if len(events) == 0:

        return None

    return events



def window_from_binary(file_path, time_start, time_end, time_anchor=None):

    """

    Extracts events from a TPWSFPGALog.bin file within a time window.



    Parameters

    ----------

    file_path : str

        Path to TPWSFPGALog.bin



    time_start : datetime

        Window start (UTC)



    time_end : datetime

        Window end (UTC)



    Returns

    -------

    list[dict]

        Decoded events with standardized ISO-8601 timestamps

    """



    START = 11

    REC = 32

    INVALID = {0xFFFFFFFF, 0}



    # ensure UTC

    if time_start.tzinfo is None:

        time_start = time_start.replace(tzinfo=timezone.utc)

    if time_end.tzinfo is None:

        time_end = time_end.replace(tzinfo=timezone.utc)



    start_ts = int(time_start.timestamp())

    end_ts = int(time_end.timestamp())



    events = []



    with open(file_path, "rb") as f:



        f.seek(0, 2)

        total_records = (f.tell() - START) // REC



        for i in range(total_records):



            f.seek(START + i * REC)

            rec = f.read(REC)



            if len(rec) < REC:

                break



            # timestamp (big endian)

            ts = struct.unpack(">I", rec[0:4])[0]



            if ts in INVALID:

                continue



            if ts < start_ts or ts > end_ts:

                continue

            time = datetime.fromtimestamp(ts, timezone.utc)

            event = {

                "timestamp": time.isoformat().replace("+00:00", "Z"),

                "event_id": struct.unpack("<H", rec[5:7])[0],

                "module": struct.unpack("<H", rec[7:9])[0],

                "flags": struct.unpack("<H", rec[9:11])[0],

                "subcode": struct.unpack("<H", rec[11:13])[0],

                "arg1": f"0x{struct.unpack('<I', rec[16:20])[0]:08x}",

                "arg2": f"0x{struct.unpack('<I', rec[20:24])[0]:08x}",

                "arg3": f"0x{struct.unpack('<I', rec[26:30])[0]:08x}",

            }



            events.append((time, event))

    if len(events) == 0:

        return None

    return events
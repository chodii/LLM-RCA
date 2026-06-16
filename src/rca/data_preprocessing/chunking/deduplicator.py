# -*- coding: utf-8 -*-

"""

Created on Sun May 10 22:42:17 2026



@author: chodo

"""

from datetime import datetime, timezone



_START_TIME_IX = 0

_END_TIME_IX = 1

_COUNT_IX = 2

_CONTENT_IX = -1



def _parse_iso(ts):

    if ts is None:

        return None



    dt = datetime.fromisoformat(ts)



    # If timestamp has no timezone, assume UTC

    if dt.tzinfo is None:

        dt = dt.replace(tzinfo=timezone.utc)



    # Normalize everything to UTC

    return dt.astimezone(timezone.utc)



def back_to_iso(ts):

    if ts is None:

        return ts

    else:

        return ts.isoformat()



def safe_to_write(line):

    if len(line) == 2:

        return [back_to_iso(line[_START_TIME_IX]), line[_CONTENT_IX]]

    else:

        return [back_to_iso(line[_START_TIME_IX])

                , back_to_iso(line[_END_TIME_IX])

                , line[_COUNT_IX]

                , line[_CONTENT_IX]]



def make_record(ts_start, ts_end, count, line):

    if count == 1:

        return [ts_start, line]

    else:

        return [ts_start, ts_end, count, line]



class Grouper:

    def __init__(self):

        self.groups = {}

        

    def add(self, row):

        if len(row) < 2:

            raise ValueError(f"Each row must have at least [timestamp, text], got: {row}")

        _ts_iso, raw_text = row[0], row[1]

        dt = _parse_iso(_ts_iso)# is iso format OR None (both are valid)

        text_hsh = str(raw_text)

        if text_hsh not in self.groups:

            self.groups[text_hsh] = [dt, dt, 1, raw_text]

            return

        if self.groups[text_hsh][_START_TIME_IX] is None or self.groups[text_hsh][_START_TIME_IX] > dt:

            self.groups[text_hsh][_START_TIME_IX] = dt

        if self.groups[text_hsh][_END_TIME_IX] is None or self.groups[text_hsh][_END_TIME_IX] < dt:

            self.groups[text_hsh][_END_TIME_IX] = dt

        self.groups[text_hsh][_COUNT_IX] += 1

    

    def get_efficiency(self):

        unrolled = 0

        for k in self.groups:

            unrolled += self.groups[k][_COUNT_IX]

        dedupted = len(self.groups)

        return unrolled, dedupted

    

    def construct_timeline_by_end(self):

        unknown_timeline = []

        timeline = []

        for k in self.groups:

            ts_start, ts_end, count, line = self.groups[k]

            record = make_record(ts_start, ts_end, count, line)

            if ts_start is None or ts_end is None:

                unknown_timeline.append(record)

            else:

                # rule: add by its last apearance

                timeline.append(record)

        timeline.sort(key=lambda record: record[_START_TIME_IX] if len(record) == 2 else record[_END_TIME_IX])

        new_timeline = []

        for line in timeline:

            new_timeline.append(safe_to_write(line))

        return unknown_timeline + new_timeline



def dedupt_row(rows):

    HanzGrouper = Grouper()

    # row: [time_start, time_end, repetitions]

    for row in rows:

        HanzGrouper.add(row)

    return HanzGrouper.construct_timeline_by_end(), HanzGrouper.get_efficiency()


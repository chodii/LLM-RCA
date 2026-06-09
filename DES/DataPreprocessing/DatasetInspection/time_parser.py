# -*- coding: utf-8 -*-
"""
Created on Wed Feb 18 15:45:51 2026

@author: chodo
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Callable

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import DatasetInspection.path_parser as path_parser
# ---------------------------------- #
# Extract year from path if missing  #
# ---------------------------------- #
SYSLOG_YEAR_COMMA_RE = re.compile(
    r"\b[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4},\s+\d{2}:\d{2}:\d{2}\b"
)
def parse_syslog_with_year_comma(
    raw: str,
    tz: ZoneInfo,
    anchor=None,
) -> Optional[datetime]:
    # raw like: "Sep  1 2015, 17:47:02"
    try:
        dt = datetime.strptime(raw.strip(), "%b %d %Y, %H:%M:%S")
    except ValueError:
        return None
    return dt.replace(tzinfo=tz)

SYSLOG_WITH_YEAR_RE = re.compile(
    r"\b[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\b"
)
def parse_syslog_with_year(
    raw: str,
    tz: ZoneInfo,
    anchor=None,
) -> Optional[datetime]:
    # raw like: "Aug  1 2022 04:00:50"
    try:
        dt = datetime.strptime(raw.strip(), "%b %d %Y %H:%M:%S")
    except ValueError:
        return None

    return dt.replace(tzinfo=tz)


FOLDER_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})_\d{2}\.\d{2}")
def parse_syslog_missing_year(
    raw: str,
    tz: ZoneInfo,
    anchor: Optional[path_parser.Anchor],
    fallback_year: int = 1970,
) -> Optional[datetime]:
    # raw like: "Mar  7 21:52:05"
    try:
        dt = datetime.strptime(raw.strip(), "%b %d %H:%M:%S")
    except ValueError:
        return None

    year = anchor.dt.year if anchor else fallback_year
    return dt.replace(year=year, tzinfo=tz)
# ----------------------------
# Helpers
# ----------------------------

def _attach_tz(dt: datetime, tz: ZoneInfo) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)

def _to_iso(dt: datetime) -> str:
    # canonical string you can later sort/filter by
    return dt.isoformat()

# ----------------------------
# Candidate timestamp extractors + parsers (ordered!)
# Each entry: (id, regex, parse_fn)
# parse_fn(raw, tz) -> datetime | None
# ----------------------------

MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
DOW = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"

def parse_iso(raw: str, tz: ZoneInfo, anchor: Optional[path_parser.Anchor]) -> Optional[datetime]:
    s = raw.strip()
    # Handle 'Z' for UTC
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        return _attach_tz(dt, tz)
    except ValueError:
        return None

def parse_short_yy_mm_dd(raw: str, tz: ZoneInfo, anchor: Optional[path_parser.Anchor]) -> Optional[datetime]:
    # ASSUMPTION: 21-12-16 = YY-MM-DD (2021-12-16)
    # If yours is DD-MM-YY, flip the format to "%d-%m-%y ..."
    for fmt in ("%y-%m-%d %H:%M:%S.%f", "%y-%m-%d %H:%M:%S", "%y-%m-%dT%H:%M:%S.%f", "%y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return _attach_tz(dt, tz)
        except ValueError:
            pass
    return None

def parse_text_with_dow(raw: str, tz: ZoneInfo, anchor: Optional[path_parser.Anchor]) -> Optional[datetime]:
    s = raw.strip().replace(" UTC", "")
    try:
        dt = datetime.strptime(s, "%a %b %d %H:%M:%S %Y")
        return _attach_tz(dt, tz)
    except ValueError:
        return None


def parse_date_only(raw: str, tz: ZoneInfo, anchor: Optional[path_parser.Anchor]) -> Optional[datetime]:
    # date-only: normalize to midnight local time
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return _attach_tz(dt, tz)
        except ValueError:
            pass
    return None


PARSERS: list[tuple[str, re.Pattern, Callable[[str, ZoneInfo], Optional[datetime]]]] = [
    (
        "short_yy-mm-dd",
        re.compile(r"\b\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b"),
        parse_short_yy_mm_dd,
    ),
    (
        "text_with_dow",
        re.compile(rf"\b{DOW}\s+{MONTHS}\s+\d{{1,2}}\s+\d{{2}}:\d{{2}}:\d{{2}}(?:\s+UTC)?\s+\d{{4}}\b"),
        parse_text_with_dow,
    ),
    ("syslog_year_comma", SYSLOG_YEAR_COMMA_RE, parse_syslog_with_year_comma),
    ("syslog_with_year", SYSLOG_WITH_YEAR_RE, parse_syslog_with_year),
    (
        "syslog_missing_year",
        re.compile(rf"\b{MONTHS}\s+\d{{1,2}}\s+\d{{2}}:\d{{2}}:\d{{2}}\b"),
        parse_syslog_missing_year,
    ),
    (
        "iso",
        re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?\b"),
        parse_iso,
    ),
    (
        "date_only",
        re.compile(r"\b(?:\d{4}|\d{2})-\d{2}-\d{2}\b"),
        parse_date_only,
    ),
    
]

# ----------------------------
# Main function
# ----------------------------

from typing import Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def normalize_line_extract_time(
    line: str,
    anchor: path_parser.Anchor
    #,tz_name: str = "Europe/London"
) -> Tuple[str, Optional[datetime], Optional[str]]:
    s = line.rstrip("\n")
    tz = timezone.utc#ZoneInfo(tz_name)

    for pid, rx, parse_fn in PARSERS:
        m = rx.search(s)
        if not m:
            continue

        raw = m.group(0)
        dt = parse_fn(raw, tz, anchor)

        normalized_line = s[:m.start()] + "<time>" + s[m.end():]

        if pid == "syslog_missing_year":
            dt2 = parse_syslog_missing_year(raw, tz, anchor, fallback_year=1970)
            if dt2 is None:
                return normalized_line, None, "syslog_missing_year"
            win = "syslog_no_year+anchor" if anchor else "syslog_no_year+1970"
            return normalized_line, dt2, win

        if dt is None:
            return normalized_line, None, pid

        return normalized_line, dt, pid

    return s, None, None



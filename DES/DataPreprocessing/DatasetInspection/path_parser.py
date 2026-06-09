# -*- coding: utf-8 -*-
"""
Created on Thu Feb 19 00:50:32 2026

@author: chodo
"""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional

# 1) 2025-03-10T21_41_04
PATH_ISO_T_US_RE = re.compile(
    r"(?P<Y>\d{4})-(?P<M>\d{2})-(?P<D>\d{2})T(?P<h>\d{2})_(?P<m>\d{2})_(?P<s>\d{2})"
)

# 2) 2025-03-10_21_41_05
PATH_ISO_US_RE = re.compile(
    r"(?P<Y>\d{4})-(?P<M>\d{2})-(?P<D>\d{2})_(?P<h>\d{2})_(?P<m>\d{2})_(?P<s>\d{2})"
)

# 3) 07.03.25_22.14  (dd.mm.yy + hh.mm)
PATH_DDMMYY_DOT_RE = re.compile(
    r"(?P<D>\d{2})\.(?P<M>\d{2})\.(?P<y>\d{2})_(?P<h>\d{2})\.(?P<m>\d{2})"
)

# 4) 10.3.25 or 10-3-25 (date only; least trusted)
PATH_DATE_LOOSE_RE = re.compile(
    r"(?P<D>\d{1,2})[.\-](?P<M>\d{1,2})[.\-](?P<y>\d{2})(?!\d)"
)

# 5) 10.3.2025 or 10-3-2025 (date only; better than #4)
PATH_DATE_LOOSE_YYYY_RE = re.compile(
    r"(?P<D>\d{1,2})[.\-](?P<M>\d{1,2})[.\-](?P<Y>\d{4})(?!\d)"
)

# 6) ..._240223 or ..._061222
# Important: only match trailing _DDMMYY at the END of the path segment,
# so we do not accidentally grab middle IDs like _710126_.
PATH_TRAILING_DDMMYY_RE = re.compile(
    r"_(?P<D>\d{2})(?P<M>\d{2})(?P<y>\d{2})$"
)

# 7) 17 Jan 23 / 17 January 23
PATH_TEXTUAL_DMY_RE = re.compile(
    r"(?P<D>\d{1,2})\s+"
    r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(?P<y>\d{2})(?!\d)",
    re.IGNORECASE,
)
# 8) "732771_720520_HMI_131122_0628\HMI2_Log\Data\Xorg.0.log.old" = 13.11.2022 06:28
# 8) ..._131122_0628  = DDMMYY_HHMM
PATH_DDMMYY_HHMM_RE = re.compile(
    r"_(?P<D>\d{2})(?P<M>\d{2})(?P<y>\d{2})_(?P<h>\d{2})(?P<m>\d{2})$"
)


def _yy_to_yyyy(yy: int) -> int:
    return 2000 + yy if yy <= 70 else 1900 + yy


def _month_to_num(mon: str) -> Optional[int]:
    m = mon.strip().lower()[:3]
    return {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }.get(m)


def _safe_dt(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    tz=None,
) -> Optional[datetime]:
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=tz)
    except ValueError:
        return None


@dataclass
class Anchor:
    dt: datetime
    score: int
    source: str
    part: str


def _update_best(
    best: Optional[Anchor],
    dt: Optional[datetime],
    score: int,
    source: str,
    part: str,
) -> Optional[Anchor]:
    if dt is None:
        return best

    cand = Anchor(dt=dt, score=score, source=source, part=part)
    if best is None or cand.score > best.score:
        return cand
    return best


# If your dataset is Swedish, Europe/Stockholm is probably the right default.
def extract_best_anchor_from_path(
    fp: str#, tz_name: str = "UTC"#"Europe/London"
) -> Optional[Anchor]:
    if not fp:
        return None

    tz = timezone.utc#ZoneInfo(tz_name)

    # Normalize separators and split into path parts
    parts = [p for p in fp.replace("/", "\\").split("\\") if p]
    best: Optional[Anchor] = None

    for idx, part in enumerate(parts):
        base = idx  # later segments win inside same trust level

        # 1) full timestamp, highest trust
        m = PATH_ISO_T_US_RE.search(part)
        if m:
            dt = _safe_dt(
                int(m["Y"]), int(m["M"]), int(m["D"]),
                int(m["h"]), int(m["m"]), int(m["s"]),
                tz=tz
            )
            best = _update_best(best, dt, base + 1000, "path_iso_T", part)
            continue

        # 2) full timestamp, high trust
        m = PATH_ISO_US_RE.search(part)
        if m:
            dt = _safe_dt(
                int(m["Y"]), int(m["M"]), int(m["D"]),
                int(m["h"]), int(m["m"]), int(m["s"]),
                tz=tz
            )
            best = _update_best(best, dt, base + 900, "path_iso_us", part)
            continue

        # 3) dd.mm.yy_hh.mm
        m = PATH_DDMMYY_DOT_RE.search(part)
        if m:
            yyyy = _yy_to_yyyy(int(m["y"]))
            dt = _safe_dt(
                yyyy, int(m["M"]), int(m["D"]),
                int(m["h"]), int(m["m"]), 0,
                tz=tz
            )
            best = _update_best(best, dt, base + 800, "path_ddmmyy_dot", part)
            continue
        
        # 8) trailing _DDMMYY_HHMM like "..._131122_0628"
        m = PATH_DDMMYY_HHMM_RE.search(part)
        if m:
            yyyy = _yy_to_yyyy(int(m["y"]))
            dt = _safe_dt(
                yyyy, int(m["M"]), int(m["D"]),
                int(m["h"]), int(m["m"]), 0,
                tz=tz
            )
            best = _update_best(best, dt, base + 750, "path_ddmmyy_hhmm", part)
            continue

        # 7) textual date like "17 Jan 23"
        # Slightly above #6 so this wins when present.
        m = PATH_TEXTUAL_DMY_RE.search(part)
        if m:
            month = _month_to_num(m["mon"])
            if month is not None:
                yyyy = _yy_to_yyyy(int(m["y"]))
                dt = _safe_dt(yyyy, month, int(m["D"]), 0, 0, 0, tz=tz)
                best = _update_best(best, dt, base + 670, "path_textual_dmy", part)
                continue

        # 6) trailing _DDMMYY like "..._240223"
        m = PATH_TRAILING_DDMMYY_RE.search(part)
        if m:
            yyyy = _yy_to_yyyy(int(m["y"]))
            dt = _safe_dt(yyyy, int(m["M"]), int(m["D"]), 0, 0, 0, tz=tz)
            best = _update_best(best, dt, base + 650, "path_trailing_ddmmyy", part)
            continue

        # 5) date-only with 4-digit year
        m = PATH_DATE_LOOSE_YYYY_RE.search(part)
        if m:
            dt = _safe_dt(
                int(m["Y"]), int(m["M"]), int(m["D"]),
                0, 0, 0, tz=tz
            )
            best = _update_best(best, dt, base + 150, "path_date_only_loose_yyyy", part)
            continue

        # 4) date-only with 2-digit year, least trusted
        m = PATH_DATE_LOOSE_RE.search(part)
        if m:
            yyyy = _yy_to_yyyy(int(m["y"]))
            dt = _safe_dt(yyyy, int(m["M"]), int(m["D"]), 0, 0, 0, tz=tz)
            best = _update_best(best, dt, base + 100, "path_date_only_loose", part)

    return best


# -*- coding: utf-8 -*-
"""
Created on Wed Apr 15 12:04:30 2026

@author: chodo
"""

from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import os

import matplotlib

def is_date_only(dt: datetime) -> bool:
    return (
        dt.hour == 0 and
        dt.minute == 0 and
        dt.second == 0 and
        dt.microsecond == 0
    )

def signed_difference_record(reported_time: datetime, actual_time: datetime) -> dict:
    diff = reported_time - actual_time

    # True only if BOTH timestamps are specific times
    from_specific_time = not is_date_only(reported_time) and not is_date_only(actual_time)

    return {
        "difference": diff,                 # timedelta
        "from_specific_time": from_specific_time
    }


def timedeltas_to_unit(values, unit="minutes"):
    if unit == "minutes":
        return [td.total_seconds() / 60.0 for td in values]
    elif unit == "hours":
        return [td.total_seconds() / 3600.0 for td in values]
    else:
        raise ValueError("unit must be 'minutes' or 'hours'")


def plot_difference_histograms(records, unit="minutes", bins=50, title="Time difference distribution"):
    font = {'size'   : 16}
    matplotlib.rc('font', **font)
    all_diffs = [r["difference"] for r in records]
    specific_diffs = [r["difference"] for r in records if r["from_specific_time"]]

    all_vals = timedeltas_to_unit(all_diffs, unit)
    specific_vals = timedeltas_to_unit(specific_diffs, unit)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].hist(all_vals, bins=bins, edgecolor="black")
    axes[0].set_title("All differences")
    axes[0].set_ylabel("Count")
    axes[0].grid(True, axis="y", alpha=0.3)

    axes[1].hist(specific_vals, bins=bins, edgecolor="black")
    axes[1].set_title("Only differences from specific times")
    axes[1].set_xlabel(f"Reported time - actual time ({unit})")
    axes[1].set_ylabel("Count")
    axes[1].grid(True, axis="y", alpha=0.3)

    fig.suptitle(title)
    plt.tight_layout()
    res_pdf = "./out/time-diff.pdf"
    os.makedirs(os.path.dirname(res_pdf), exist_ok=True)
    plt.savefig(res_pdf)
    plt.show()
import matplotlib.pyplot as plt
from datetime import datetime

data_orig = {
    '2021': {'12': 511352},
    '2025': {'03': 3887981, '02': 3918988, '01': 3752490},
    '2024': {'09': 107324, '02': 163944, '01': 111966, '11': 108684,
             '03': 83784, '04': 87822, '05': 79264, '06': 92794,
             '07': 96850, '08': 88566, '10': 87356, '12': 69420},
    '2022': {'08': 60},
    '2015': {'03': 60, '05': 60, '09': 1},
    '2023': {'12': 14160, '01': 8},
    '2011': {'10': 16},
    '2002': {'01': 16},
    '2010': {'12': 16},
    '2019': {'03': 266516}
}

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from datetime import datetime

def plot_data(data_orig, tag = None, show=False):
    items = []
    if tag is None:
        tag = ""

    for year, months in data_orig.items():
        for month, count in months.items():
            dt = datetime(int(year), int(month), 1)
            items.append((dt, count))

    items.sort(key=lambda x: x[0])

    dates = [x[0] for x in items]
    values = [x[1] for x in items]

    present_years = sorted({dt.year for dt in dates})
    tick_positions = [datetime(year, 1, 1) for year in present_years]
    tick_labels = [str(year) for year in present_years]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # top: linear
    ax1.bar(dates, values, width=25)
    ax1.set_ylabel("Event count")
    ax1.set_title("Monthly event distribution"+tag)
    if tag is not None:
        tag = tag.strip().replace(".", "")
    
    # bottom: log
    ax2.bar(dates, values, width=25)
    ax2.set_yscale("log")
    ax2.set_ylabel("Event count (log scale)")
    ax2.set_xlabel("Year")

    # x ticks only on the shared bottom axis
    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels(tick_labels, rotation=45)

    plt.tight_layout()
    plt.savefig(tag+"hist_both.pdf")
    if show:
        plt.show()

#plot_data(data_orig)

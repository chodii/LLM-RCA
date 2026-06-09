# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 14:28:59 2026

@author: chodo
"""

import os
import re
from collections import Counter
from datetime import datetime
import matplotlib.pyplot as plt

DEST = "./"

def incident_distribution_from_folders(root_folder, show=False):
    os.makedirs(DEST, exist_ok=True)

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    dates = []

    # collect folder names that look like YYYY-MM-DD
    for current_root, dirnames, _ in os.walk(root_folder):
        for d in dirnames:
            if date_pattern.match(d):
                try:
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    dates.append(dt)
                except ValueError:
                    pass  # skip invalid dates like 2022-02-31

    if not dates:
        raise ValueError("No subfolders with valid YYYY-MM-DD names were found.")

    # count per year and per month
    yearly_counts = Counter(dt.strftime("%Y") for dt in dates)
    monthly_counts = Counter(dt.strftime("%Y-%m") for dt in dates)

    yearly_labels = sorted(yearly_counts.keys())
    yearly_values = [yearly_counts[k] for k in yearly_labels]

    monthly_labels = sorted(monthly_counts.keys())
    monthly_values = [monthly_counts[k] for k in monthly_labels]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # yearly
    ax1.bar(yearly_labels, yearly_values, edgecolor="black")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Incident count")
    ax1.set_title("Incident distribution - yearly")

    # monthly
    ax2.bar(monthly_labels, monthly_values, edgecolor="black")
    ax2.set_xlabel("Month")
    ax2.set_ylabel("Incident count")
    ax2.set_title("Incident distribution - monthly")
    plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")

    plt.suptitle("Incident distribution")
    plt.tight_layout()

    out_path = os.path.join(DEST, "Incident distribution.pdf")
    plt.savefig(out_path, format="pdf")
    if show:
        plt.show()
    plt.close()

    return out_path

def main():
    incident_distribution_from_folders(f"C:\Datasets\mon-lis-PROCESSED", show=True)
if __name__ == "__main__":
    main()
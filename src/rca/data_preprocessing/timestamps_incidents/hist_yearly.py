# -*- coding: utf-8 -*-

"""

Created on Sat Mar  7 17:24:16 2026



@author: chodo

"""



import matplotlib.pyplot as plt



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



def plot_data(data_orig, log=True, tag=None, show=False):

    # ---- aggregate yearly counts ----

    year_counts = {}

    if tag is None:

        tag = ""

    for year, months in data_orig.items():

        year_counts[int(year)] = sum(months.values())

    

    # sort years

    years = sorted(year_counts.keys())

    values = [year_counts[y] for y in years]

    

    # ---- plot ----

    plt.figure(figsize=(12,6))

    

    plt.bar(years, values, width=0.8)

    

    plt.xlabel("Year")

    plt.ylabel("Event count")

    plt.title("Yearly event distribution"+tag)

    if tag is not None:

        tag = tag.strip().replace(".", "")

    plt.xticks(years, rotation=45)

    

    plt.tight_layout()

    plt.savefig(tag+"hist_year.pdf")

    

    # log version

    plt.yscale("log")

    plt.ylabel("Event count (log scale)")

    plt.savefig(tag+"hist_year_log.pdf")

    if show:

        plt.show()
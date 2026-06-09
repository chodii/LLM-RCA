# -*- coding: utf-8 -*-
"""
Created on Wed Mar 25 01:11:09 2026

@author: chodo
"""
import os
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

DEST = "./out/"

def hist_from_array(array, x, y, title, bins=30, dest=None, show=False):
    font = {'size'   : 16}
    matplotlib.rc('font', **font)
    
    os.makedirs(DEST, exist_ok=True)
    if dest is None:
        dest = DEST

    data = np.asarray(array, dtype=float)
    data = data[np.isfinite(data)]  # remove NaN / inf
    # if OUTLIERS is not None: plot data < OUTLIERS normally and group all data>OUTLIERS into the most right column that says outliers
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
    
    # Normal histogram
    ax1.hist(data, bins=bins, edgecolor="black")
    ax1.set_xlabel(x)
    ax1.set_ylabel(y)
    ax1.set_title(title)

    # Same histogram, but logarithmic y-axis
    ax2.hist(data, bins=bins, edgecolor="black")
    ax2.set_xlabel(x)
    ax2.set_ylabel(y)
    ax2.set_title(title + " (log)")
    ax2.set_yscale("log")

    plt.tight_layout()

    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
    out_path = os.path.join(dest, safe_title + ".pdf")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    plt.savefig(out_path, format="pdf")
    if show:
        plt.show()
    plt.close()

    return out_path

def hist_from_array_single(array, x, y, title, bins=30, show=False, dest=None):
    font = {'size'   : 16}
    matplotlib.rc('font', **font)
    print("\n",title,"\tmean:", sum(array)/len(array))
    if dest is None:
        dest = DEST
    os.makedirs(dest, exist_ok=True)

    data = np.asarray(array, dtype=float)
    data = data[np.isfinite(data)]  # remove NaN / inf
    # if OUTLIERS is not None: plot data < OUTLIERS normally and group all data>OUTLIERS into the most right column that says outliers
    fig, (ax1) = plt.subplots(1, 1, figsize=(12, 6))
    
    # Normal histogram
    ax1.hist(data, bins=bins, edgecolor="black")
    ax1.set_xlabel(x)
    ax1.set_ylabel(y)
    ax1.set_title(title)

    plt.tight_layout()

    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
    out_path = os.path.join(dest, safe_title + ".pdf")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    plt.savefig(out_path, format="pdf")
    if show:
        plt.show()
    plt.close()

    return out_path


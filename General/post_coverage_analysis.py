# -*- coding: utf-8 -*-
"""
Created on Mon May  4 17:37:16 2026

@author: chodo
"""
import sys
import json
import os
from pathlib import Path
from matplotlib import pyplot as plt

def avg_coverage(src_path, mode):
    src_path = os.path.abspath(src_path)
    if not os.path.exists(src_path):
        return None
    with open(src_path, "r", encoding="utf-8") as fp:
        coverage = json.load(fp).get(mode, None)
        if coverage is None:
            return None
    chunks = []
    for k in coverage:
        chunks.append(len(coverage[k]))
    return sum(chunks)/len(chunks)

def coverage_anal(root, mode):
    outs = {}
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        fp = folder / "coverage_analysis.json"
        avg = avg_coverage(fp, mode)
        if avg is None:
            continue
        outs[folder.name] = avg
    return outs

import matplotlib.pyplot as plt

def plot_cov_anal(DEST, outs, mode):
    coverage = {}

    for k, v in outs.items():
        if "chunked_" in k:
            chunk_size = int(k.replace("chunked_", ""))
            coverage[chunk_size] = v

        elif "windowed_selection" in k:
            coverage["original"] = v

    chunk_keys = sorted(k for k in coverage.keys() if isinstance(k, int))
    has_original = "original" in coverage

    x_chunks = chunk_keys
    y_chunks = [coverage[k] for k in chunk_keys]

    fig, ax = plt.subplots(figsize=(9, 5))

    # Width based on the smallest chunk-size distance
    if len(chunk_keys) > 1:
        min_gap = min(b - a for a, b in zip(chunk_keys[:-1], chunk_keys[1:]))
    else:
        min_gap = chunk_keys[0] * 0.2 if chunk_keys else 1

    bar_width = min_gap * 0.6

    # Plot real chunk sizes on a real numeric x-axis
    ax.bar(
        x_chunks,
        y_chunks,
        width=bar_width,
        edgecolor="black",
        label="chunked data"
    )

    xticks = list(x_chunks)
    xticklabels = [str(x) for x in x_chunks]

    if has_original:
        # Put original after the largest numeric chunk, with extra space
        x_original = max(chunk_keys) + 2 * min_gap
        y_original = coverage["original"]

        # Separator line between chunked data and original data
        sep_x = max(chunk_keys) + min_gap
        ax.axvline(sep_x, linestyle="--", linewidth=1)

        ax.bar(
            x_original,
            y_original,
            width=bar_width,
            edgecolor="black",
            color="gray",
            label="original files"
        )

        xticks.append(x_original)
        xticklabels.append("original files")

    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, rotation=30, ha="right")

    ax.set_xlabel("Chunk size")
    ax.set_ylabel("Average number of relevant sources")
    if mode == "files":
        title = "Spread of unique relevant information across chunks"
    if mode == "files_all":
        title = "Number of chunks that contain potentially relevant information"
    ax.set_title(title)
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.5)

    ax.legend()
    fig.tight_layout()
    fig.savefig(DEST / ("postcoverage-analysis-"+mode+".pdf"))
    plt.show()
    
def main():
    dest = "out/"
    mode = "files"
    if len(sys.argv) > 1:
        dest = sys.argv[1]
        if len(sys.argv) > 2:
            mode = sys.argv[2]
    
    root = Path(dest)
    outs = coverage_anal(root, mode)
    plot_cov_anal(root,outs, mode)
    

if __name__ == "__main__":
    main()
    
# -*- coding: utf-8 -*-

"""

Created on Tue Apr 28 16:08:34 2026



@author: chodo

"""



from pathlib import Path

import numpy as np

import matplotlib.pyplot as plt





def _clean_lengths(line_lengths):

    arr = np.asarray(line_lengths, dtype=float)

    arr = arr[np.isfinite(arr)]



    if arr.size == 0:

        raise ValueError("line_lengths is empty after filtering non-finite values.")



    if np.any(arr < 0):

        raise ValueError("line_lengths must contain non-negative values only.")



    return arr





def plot_line_length_hist_grid(

    line_lengths,

    bins=50,

    title="Line length distribution",

    out_path=None,

    show=True,

):

    """

    Plot a 2x2 grid of histograms for all combinations of:

        log_x = False / True

        log_y = False / True



    Notes:

    - For log_x plots, values are shifted by +1 so zero-length values can be shown.

    """



    lengths = _clean_lengths(line_lengths)



    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    combos = [

        (False, False),

        (True,  False),

        (False, True),

        (True,  True),

    ]



    for ax, (log_x, log_y) in zip(axes.ravel(), combos):

        if log_x:

            # shift by +1 so zeros can appear on a log-x axis

            plot_values = lengths + 1



            if plot_values.min() == plot_values.max():

                bin_edges = np.array([plot_values[0] - 0.5, plot_values[0] + 0.5])

            else:

                bin_edges = np.logspace(

                    np.log10(plot_values.min()),

                    np.log10(plot_values.max()),

                    bins + 1

                )



            ax.hist(plot_values, bins=bin_edges, edgecolor="black")

            ax.set_xscale("log")

            ax.set_xlabel("Line length")# (+1 for log-x plot)

        else:

            ax.hist(lengths, bins=bins, edgecolor="black")

            ax.set_xlabel("Line length")



        if log_y:

            ax.set_yscale("log")



        ax.set_ylabel("Count")

        ax.set_title(f"log_x={log_x}, log_y={log_y}")



    fig.suptitle(title)

    fig.tight_layout(rect=[0, 0, 1, 0.96])



    if out_path is not None:

        out_path = Path(out_path)

        out_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(out_path, bbox_inches="tight")



    if show:

        plt.show()



    return fig, axes



def plot_line_length_hist_with_outlier_bin(

    line_lengths,

    OUTLIER_LIMIT,

    bins=50,

    title="Line length distribution with outlier bin",

    out_path=None,

    show=True,

    bin_num=5

):

    """

    Plot two histograms above each other:

        - normal y scale

        - log y scale



    Values > OUTLIER_LIMIT are grouped into the rightmost 'outlier' bin.

    """



    lengths = _clean_lengths(line_lengths)



    if OUTLIER_LIMIT <= 0:

        raise ValueError("OUTLIER_LIMIT must be > 0.")



    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)



    # Regular bins from 0 to OUTLIER_LIMIT

    regular_edges = np.linspace(0, OUTLIER_LIMIT, bins + 1)



    # Add one extra bin for outliers

    extra_width = regular_edges[1] - regular_edges[0]

    overflow_left = regular_edges[-1]

    overflow_right = overflow_left + extra_width

    overflow_center = (overflow_left + overflow_right) / 2



    # Move all outliers into the extra bin

    clipped = np.where(lengths > OUTLIER_LIMIT, overflow_center, lengths)

    all_edges = np.append(regular_edges, overflow_right)



    for ax, log_y in zip(axes, [False, True]):

        ax.hist(clipped, bins=all_edges, edgecolor="black")

        ax.set_ylabel("Count")

        ax.set_title(f"log_y={log_y}")



        if log_y:

            ax.set_yscale("log")



        ax.axvline(OUTLIER_LIMIT, linestyle="--")



    axes[-1].set_xlabel("Line length")



    # Make x-ticks readable, including the outlier bin

    tick_positions = list(np.linspace(0, OUTLIER_LIMIT-int(OUTLIER_LIMIT/bin_num), bin_num)) + [overflow_center]

    tick_labels = [str(int(x)) for x in np.linspace(0, OUTLIER_LIMIT-int(OUTLIER_LIMIT/bin_num), bin_num)] + [f">{OUTLIER_LIMIT}"]



    axes[-1].set_xticks(tick_positions)

    axes[-1].set_xticklabels(tick_labels)



    fig.suptitle(f"{title} (values > {OUTLIER_LIMIT} grouped into final bin)")

    fig.tight_layout(rect=[0, 0, 1, 0.96])



    if out_path is not None:

        out_path = Path(out_path)

        out_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(out_path, bbox_inches="tight")



    if show:

        plt.show()



    return fig, axes











from pathlib import Path

import numpy as np

import matplotlib.pyplot as plt





def plot_line_length_cdf(

    line_lengths,

    title="Cumulative distribution of line lengths",

    out_path=None,

    show=True,

    complementary=False,   # False = CDF, True = CCDF

):

    """

    Plot empirical CDF / CCDF of line lengths with logarithmic x-axis.



    Parameters

    ----------

    line_lengths : iterable of numbers

        Non-negative line lengths.

    title : str

        Plot title.

    out_path : str or Path or None

        Optional save path.

    show : bool

        Whether to show the plot.

    complementary : bool

        If False: plot CDF = P(X <= x)

        If True:  plot CCDF = P(X >= x)

    """



    lengths = _clean_lengths(line_lengths)



    # log-x cannot display zero, so shift by +1

    x = np.sort(lengths + 1)

    n = len(x)



    if complementary:

        # CCDF: proportion >= x

        y = np.arange(n, 0, -1) / n

        ylabel = "P(X ≥ x)"

        plot_title = title + " (CCDF)"

    else:

        # CDF: proportion <= x

        y = np.arange(1, n + 1) / n

        ylabel = "P(X ≤ x)"

        plot_title = title + " (CDF)"



    plt.figure(figsize=(10, 6))

    plt.step(x, y, where="post")

    plt.xscale("log")



    plt.xlabel("Line length")# (+1 for log-x plot)

    plt.ylabel(ylabel)

    plt.title(plot_title)

    plt.grid(True, which="both", alpha=0.3)

    plt.tight_layout()



    if out_path is not None:

        out_path = Path(out_path)

        out_path.parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(out_path, bbox_inches="tight")



    if show:

        plt.show()
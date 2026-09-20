
import os
import statistics as st
from rca.results import xBinTable as xb
import rca.results.Logger as log
from pathlib import Path
import matplotlib.pyplot as plt
import math

from scipy.stats import wilcoxon
import numpy as np

def bar_diffs_viz(dest, data, tag, name):
    x = np.arange(len(data))
    improvements = np.array([d["improved"] for d in data])
    declines = np.array([d["worsened"] for d in data])
    tradeoffs = np.array([d["unchanged"] for d in data])
    fig, ax = plt.subplots(figsize=(7, 6))
    # Stacked bars
    ax.bar(x, declines, label="Worsened", color="#E53935")
    ax.bar(x, tradeoffs, bottom=declines, label="Unchanged", color="#9E9E9E")
    ax.bar(
        x,
        improvements,
        bottom=declines + tradeoffs,
        label="Improved",
        color="#4CAF50"
    )
    # Numbers
    for i in range(len(x)):
        if declines[i]:
            ax.text(
                x[i],
                declines[i] / 2,
                str(declines[i]),
                ha="center",
                va="center"
            )
        if tradeoffs[i]:
            ax.text(
                x[i],
                declines[i] + tradeoffs[i] / 2,
                str(tradeoffs[i]),
                ha="center",
                va="center"
            )
        if improvements[i]:
            ax.text(
                x[i],
                declines[i] + tradeoffs[i] + improvements[i] / 2,
                str(improvements[i]),
                ha="center",
                va="center"
            )
    ax.set_xticks(x)
    ax.set_xticklabels(["Retrieval", "Summarization", "Final output"])
    ax.set_ylabel("Count")
    ax.set_xlabel("Component")
    ax.set_title("Sample-wise impact " + tag + "")
    ax.legend()
    plt.tight_layout()
    plt.savefig(dest + name + " bar"+"diffs.pdf")
    plt.close()

def print_latex_table(experiment_name, experiment, label_suffix):
    """
    Print a LaTeX table containing recall mean and variance
    over all repeated observations.
    """

    components = ["Retrieval", "Summarization", "Final output"]

    print()
    print("% ============================================================")
    print(f"% {experiment_name}")
    print("% ============================================================")

    print(r"\begin{table}[]")
    print(r"    \centering")
    print(r"    \begin{tabular}{c|c|c|c|c}")
    print(r"        Ground truth & Aspect & Retrieval [\%] & Summarization [\%] & Final output [\%] \\")
    print(r"        \hline")

    for target, target_name in [
        ("reference", "ref. RCA"),
        ("line2_exact", "grnd. ref."),
    ]:
        for aspect, aspect_name in [
            ("line_count", "line cnt."),
            ("line_lengths", "line len."),
        ]:
            # Skip if this target does not exist
            if target not in experiment:
                continue

            values = []

            for component in components:
                stats = experiment[target][aspect][component]
                mean = stats["overall_mean"] * 100
                overall_std = stats["overall_std"] * 100
                within_sample_std = math.sqrt(stats["mean_sample_variance"]) * 100

                values.append(
                    f"{mean:.1f} $\\pm$ {overall_std:.1f}"
                    f" [{within_sample_std:.1f}]"
                )
            print(
                f"       {target_name} & {aspect_name} &  "
                f"{values[0]} & {values[1]} & {values[2]} \\\\"
            )

    print(r"    \end{tabular}")
    print(
        r"    \caption{(\textbf{Recall $\pm$ std [within-sample std]}) Recall of the AI agent's components by aspect and ground truth. Values show the mean $\pm$ standard deviation across all observations; values in square brackets show the mean within-sample standard deviation, indicating variability across repeated executions of the same incident. The grounded reference (grnd. ref.) comprises reference RCA lines that could be grounded in the available dataset; ref. RCA corresponds to the original reference RCA; line cnt. stands for line count, and line len. for line length.}"
    )
    print(f"    \label{{tab:performance-{label_suffix}}}")
    print(r"\end{table}")
    print()

def latex_stat_tables(all_stat_res):

    # =========================================================
    # BIG TABLE
    # =========================================================

    print(r"""
\begin{table}[]
    \centering
    \begin{tabular}{l|l|r|r|r|r|r|r}
        Comparison & Component & Mean $\Delta$ & $W$ & $p$ &
        Improved & Unchanged & Worsened \\
        \hline
""")

    for comparison, components in all_stat_res.items():
        for component, result in components.items():
            print(
                f"        {comparison} & {component} & "
                f"{result['mean_difference']:.4f} & "
                f"{result['statistic']:.2f} & "
                f"{result['p_value']:.4g} & "
                f"{result['improved']} & "
                f"{result['unchanged']} & "
                f"{result['worsened']} \\\\"
            )

    print(r"""    \end{tabular}
    \caption{Comparison of experiment versions using the paired Wilcoxon signed-rank test. Mean $\Delta$ denotes the mean difference between the compared versions. $W$ is the Wilcoxon signed-rank statistic. Improved, unchanged, and worsened denote the number of incidents for which the respective change was observed.}
    \label{tab:statistical-comparison}
\end{table}
""")


    # =========================================================
    # THREE SEPARATE TABLES
    # =========================================================

    for comparison, components in all_stat_res.items():

        print("\n\n")
        print(r"\begin{table}[]")
        print(r"    \centering")
        print(r"""    \begin{tabular}{l|r|r|r|r|r|r}
        Component & Mean $\Delta$ & $W$ & $p$ &
        Improved & Unchanged & Worsened \\
        \hline""")

        for component, result in components.items():
            print(
                f"        {component} & "
                f"{result['mean_difference']:.4f} & "
                f"{result['statistic']:.2f} & "
                f"{result['p_value']:.4g} & "
                f"{result['improved']} & "
                f"{result['unchanged']} & "
                f"{result['worsened']} \\\\"
            )

        print(r"""    \end{tabular}""")
        print(
            f"    \\caption{{Statistical comparison: "
            f"{comparison}.}}"
        )
        print(
            f"    \\label{{tab:statistical-"
            f"{comparison.lower().replace(' ', '-').replace(' - ', '-')}}}"
        )
        print(r"\end{table}")

def test_versions(a, b):
    differences = [b_i - a_i for a_i, b_i in zip(a, b)]
    result = wilcoxon(a, b)
    return {
        "statistic": result.statistic,
        "p_value": result.pvalue,
        "mean_difference": st.mean(differences),
        "improved": sum(d > 0 for d in differences),
        "unchanged": sum(d == 0 for d in differences),
        "worsened": sum(d < 0 for d in differences),
    }

def test_experiments(experiments, k, aspect, dest):
    keys = list(experiments.keys())
    all_stat_res = {}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            res = {}
            results = []
            for component in ["Retrieval", "Summarization", "Final output"]:
                before_sample = get_sample_means(
                    experiments[keys[i]], k, aspect, component
                )
                optimized_sample = get_sample_means(
                    experiments[keys[j]], k, aspect, component
                )
                result = test_versions(
                    before_sample,
                    optimized_sample
                )
                results.append(result)
                res[component]=result
            all_stat_res[keys[i] + " - " + keys[j]] = res
            tag = (
                keys[i]
                + " vs "
                + keys[j]
                + " - "
                + aspect
                + " "
                + k.replace("line2_exact", "grounded reference")
            )
            invtag = (
                k
                + "-"
                + aspect
                + " "
                + keys[i]
                + "-"
                + keys[j]
            )
            bar_diffs_viz(
                dest,
                data=results,
                tag=tag
                ,name=invtag
            )
    print(k+" - "+aspect)
    latex_stat_tables(all_stat_res)

def statistics(sep_arr):
    """
    sep_arr:
        list of experiment runs

        sep_arr[run][metric][sample]
    """
    SEPS = {}
    # Rearrange:
    # SEPS[metric][sample] = [value_run1, value_run2, ...]
    for sep in sep_arr:
        for k in sep:
            if k not in SEPS:
                SEPS[k] = []
            for i in range(len(sep[k])):
                if len(SEPS[k]) <= i:
                    SEPS[k].append([])
                SEPS[k][i].append(sep[k][i])
    stats = {}
    for k in SEPS:
        # ---- Per-sample statistics ----
        sample_stats = []
        for i, values in enumerate(SEPS[k]):
            sample_stats.append({
                "mean": st.mean(values),
                "variance": st.variance(values) if len(values) > 1 else 0.0,
                "std": st.stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
            })
        # ---- Whole repeated experiment set ----
        # Flatten all observations
        all_values = [
            value
            for sample in SEPS[k]
            for value in sample
        ]
        # Means of individual samples
        sample_means = [
            sample["mean"]
            for sample in sample_stats
        ]
        # Variance within repetitions of the same sample
        sample_variances = [
            sample["variance"]
            for sample in sample_stats
        ]
        stats[k] = {
            "samples": sample_stats,
            # All individual observations
            "overall_mean": st.mean(all_values),
            "overall_variance": (
                st.variance(all_values)
                if len(all_values) > 1 else 0.0
            ),
            "overall_std": (
                st.stdev(all_values)
                if len(all_values) > 1 else 0.0
            ),

            # Distribution of sample means
            "sample_mean_mean": st.mean(sample_means),
            "sample_mean_variance": (
                st.variance(sample_means)
                if len(sample_means) > 1 else 0.0
            ),
            "sample_mean_std": (
                st.stdev(sample_means)
                if len(sample_means) > 1 else 0.0
            ),
            # Average variability between repeated runs
            "mean_sample_variance": st.mean(sample_variances),
        }
    return stats



def statist(pths):
    seps = {}
    ASPECTS=["line_count", "line_lengths"]
    costs = []
    for pth in pths:
        trans = log.transform(pth)
        usages = trans["usages"]
        costs.extend(usages)
        evaluations = xb.evaluate_samples(trans, SUB=True)
        evs_samplewise = xb.grounded_information_SOLO_sample_wise(evaluations=evaluations, trans=trans, ONLY_GROUNDED=True)
        for k in evs_samplewise:# TARGETS
            if k not in seps:
                seps[k] = {}
            for Aspect in ASPECTS:
                if Aspect not in seps[k]:
                    seps[k][Aspect] = []
                sep = xb.eve_to_dict(evs_samplewise[k][Aspect])
                seps[k][Aspect].append(sep)
    # statistics
    stats = {}
    for k in seps:
        #print(k)
        stats[k]={}
        for Aspect in ASPECTS:
            #print("\t",Aspect)
            stats[k][Aspect] = statistics(seps[k][Aspect])
            #for s in stats[k][Aspect]:
            #    print("\t\t",s,stats[k][Aspect][s])
    
    print("\ttotal", sum(costs),
        "\n\taverage", sum(costs) / len(costs),
        "\n\tcount", len(costs))
    return stats

def compare(a, b):
    differences = [
        b_i - a_i
        for a_i, b_i in zip(a, b)
    ]
    return {
        "differences": differences,
        "mean_difference": st.mean(differences),
        "improved": sum(d > 0 for d in differences),
        "unchanged": sum(d == 0 for d in differences),
        "worsened": sum(d < 0 for d in differences),
    }

def get_sample_means(experiment, k, aspect, component):
    return [
        sample["mean"]
        for sample in experiment[k][aspect][component]["samples"]
    ]

def get_results(root):
    return [
        str(p)+"/LOGGER.json"
        for p in Path(root).iterdir()
        if p.is_dir()
    ]


from rca.results.rouge import rouge_analysis

def main():
    experiments = {
        "Before PO": statist(get_results("out/chunked_3000_PO-before/")),
        "Optimized": statist(get_results("out/chunked_3000_PO-after/")),
        "Optimized + extended retrieval": statist(get_results("out/chunked_3000/")),
    }
    outdir="out/statistics/"
    os.makedirs(outdir, exist_ok=True)
    rouge_analysis(
        get_results("out/chunked_3000/"),
        dest=outdir
    )
    for name, experiment in experiments.items():
        print_latex_table(
            name,
            experiment,
            name.lower().replace(" ", "-")
        )
    dicts = []
    labels = []
    for k in experiments:
        dicts.append({comp: st.mean(get_sample_means(experiments[k], "reference", "line_count", comp)) for comp in experiments[k]["reference"]["line_count"]})
        labels.append(k)
        xb.pr.plot_radar_generic(dicts=dicts, labels=labels, title="Radar chart - "+k.replace("line2_exact", "grounded reference")+" (ref. RCA - line cnt.)", dest=outdir)
        
    for k in experiments["Before PO"]:
        if k == "line_contained":# obsolete
            continue
        for aspect in ["line_count", "line_lengths"]:
            #print(aspect)
            for component in ["Retrieval", "Summarization", "Final output"]:
                #print(component)
                data = [
                    get_sample_means(experiments["Before PO"], k, aspect, component),
                    get_sample_means(experiments["Optimized"], k, aspect, component),
                    get_sample_means(experiments["Optimized + extended retrieval"], k, aspect, component),
                ]
                plt.figure()
                plt.boxplot(
                    data,
                    tick_labels=["Before PO", "Optimized", "Optimized + extended retrieval"]
                )
                plt.ylabel("Recall")
                plt.title(f"{component} ({k.replace("line2_exact", "grounded reference")} {aspect.replace("_", " ")})")
                plt.savefig(outdir+k+"-"+aspect.replace("_", " ")+"-"+component+".pdf")
                #plt.show()
                plt.close()
            test_experiments(experiments, k, aspect, dest=outdir)

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Created on Tue May 12 13:31:10 2026

@author: chodo
"""
import argparse
import json

import numpy as np
import matplotlib.pyplot as plt
import os

def plot_radar(dict_a, dict_b, label_a, label_b, title, dest, show=False):
    # Ensure both dictionaries have the same keys
    if set(dict_a.keys()) != set(dict_b.keys()):
        raise ValueError("Both dictionaries must have the same keys.")

    labels = list(dict_a.keys())

    values_a = [dict_a[k] for k in labels]
    values_b = [dict_b[k] for k in labels]

    # Close the radar loop by repeating the first value
    values_a += values_a[:1]
    values_b += values_b[:1]

    # Angles for each axis
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    ax.plot(angles, values_a, linewidth=2, label=label_a)
    ax.fill(angles, values_a, alpha=0.25)

    ax.plot(angles, values_b, linewidth=2, label=label_b)
    ax.fill(angles, values_b, alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)

    ax.set_title(title, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))

    ax.grid(True)

    plt.tight_layout()
    safename = title.replace(" ", "").replace("'s","")
    dest = dest+safename
    plt.savefig(fname=dest+".pdf")
    if show:
        plt.show()


from pathlib import Path

def plot_hist(values, title, dest=None, xlabel="Recall", bins=30):
    if not values:
        raise ValueError("No valid numeric values found to plot.")

    plt.figure(figsize=(8, 5))
    plt.hist(values, bins=bins, edgecolor="black")

    plt.xlabel(xlabel=xlabel)
    plt.ylabel("Count")
    plt.title(title)

    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    name = title.replace(" ", "")
    if dest is not None:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(dest / (name+".pdf"), dpi=300)
        plt.close()
    else:
        plt.show()

def flatten(arr_a, NORMALIZED):
    data = []
    for d in arr_a:
        if NORMALIZED:
            if d[1] == 0:
                print("ERROR", d)
            else:
                s = d[0]/d[1] 
        else:
            s = d[0]
        data.append(s)
    return data

import statistics
def show_separate(ret_comp, agent_comp, NORMALIZED, dest):
    tag = " - normalized" if NORMALIZED else ""
    title = "Recall distribution"
    for k in ret_comp:
        values = flatten(ret_comp[k], NORMALIZED=NORMALIZED)
        print("retr median:",k, statistics.median(values))
        plot_hist(values=values, title=title+"["+k+"] of the retriever"+tag, dest=dest)
    for k in agent_comp:
        values = flatten(agent_comp[k], NORMALIZED=NORMALIZED)
        print("agent median:",k, statistics.median(values))
        plot_hist(values=values, title=title+"["+k+"] of the agent"+tag, dest=dest)

def calc_recall(data, k, tag, NORMALIZED):
    achieved = 0
    target_cov = 0
    for i in range(len(data)):
        achieved += data[i][0]
        target_cov += data[i][1]
    print(tag+" "+k+": recalled", achieved/len(data), ",\ttarget", target_cov/len(data))
    if NORMALIZED:
        recall = achieved/target_cov
    else:
        recall = achieved/len(data)
    print(k+":",recall)
    return recall

def trans_comps(comparisons):
    transformed_comp = {}
    for comp in comparisons:
        for k in comp:
            if k not in transformed_comp:
                transformed_comp[k] = []
            transformed_comp[k].append(comp[k])
    return transformed_comp

def compare(transformed_comp, tag, normalization):
    recalls = {}
    for k in transformed_comp:
        rcll = calc_recall(data=transformed_comp[k], k=k, tag=tag, NORMALIZED=normalization)
        recalls[k] = rcll
    return recalls

def get_cont(res_file_name):
    with open(res_file_name, "r", encoding="utf-8") as fp:
        res = json.load(fp)
    dest = res_file_name.replace("\\","/")
    filename = dest.split("/")[-1]
    dps = dest.split(filename)
    dest = dps[0]+filename.split(".")[0]+"/"
    print("=>", dest)
    os.makedirs(dest, exist_ok=True)
    return res, dest

def show_comparisons(res, dest):
    
    ret_comparisons = res["retriever_compared_metrics"]
    ret_comparisons = trans_comps(ret_comparisons)

    agent_comparisons = res["agent_compared_metrics"]
    agent_comparisons = trans_comps(agent_comparisons)

    #dest = dest.split(dest.split("/")[-1])[0]
    for normalization in [True, False]:
        note = ("Normalized" if normalization else "Absolute")
        print("\n","="*16,note, "="*16)
        retr_rec = compare(transformed_comp=ret_comparisons, tag="Retriever", normalization=normalization)
        print()
        agent_rec = compare(transformed_comp=agent_comparisons, tag="Agent", normalization=normalization)
        plot_radar(dict_a=retr_rec, dict_b=agent_rec, label_a="Retriever", label_b="Agent", title="Retriever's and Agent's Recall ("+note+")", dest=dest)
        show_separate(ret_comp=ret_comparisons, agent_comp=agent_comparisons, NORMALIZED=normalization, dest=dest)

def parse_args():
    parser = argparse.ArgumentParser(
       description="Processing of the results.json file"
       )
    parser.add_argument(
         "-r", "--results",
         dest="results",
         default="results.json"
         ,help="The results.json file"
     )
    args = parser.parse_args()
    return args.results

def show_usage(res, dest):
    usage = res["samples"]["usage-rounds"]
    plot_hist(values=usage, title="Conversation rounds distribution", dest=dest, xlabel="Rounds")

def main():
    resultsfile = parse_args()
    res, dest = get_cont(res_file_name=resultsfile)
    show_comparisons(res, dest)
    show_usage(res, dest)

if __name__ == "__main__":
    main()

import rca.results.Logger as log
import sys
import rca.results.proc_results as pr
from pathlib import Path
import numpy as np
import re
from matplotlib import pyplot as plt
import os


def sub_evaluate_txt(inps, respect_ix):
    inps_prep = []
    for inp in inps:
        inps_prep.append(log.prep(inp))
    resp_inps = []
    for sample in inps_prep[respect_ix]:
        samp_bin = []
        for i in range(len(inps_prep)):
            if i == respect_ix:
                samp_bin.append(True)# always has been
                continue
            for j in range(len(inps_prep[i])):
                if sample in inps_prep[i][j]:
                    samp_bin.append(True)
            else:
                samp_bin.append(False)
        resp_inps.append(samp_bin)
        #print(samp_bin)
    return resp_inps

def cross_evaluate_txt(inps, respect_ix):
    inps_prep = []
    for inp in inps:
        inps_prep.append(log.prep(inp))
    resp_inps = []
    for sample in inps_prep[respect_ix]:
        samp_bin = []
        for i in range(len(inps_prep)):
            if i == respect_ix:
                samp_bin.append(True)# always has been
                continue
            if sample in inps_prep[i]:
                samp_bin.append(True)
            else:
                samp_bin.append(False)
        resp_inps.append(samp_bin)
        #print(samp_bin)
    return resp_inps

def evaluate_samples(trans, SUB=True):
    LABELS = ["input", "retrieved", "assistant", "generated", "reference", "line2_exact", "line_contained"]
    aspects = {}
    for l in LABELS:
        for i in range(len(trans[l])):
            trans[l][i] = log.prep(trans[l][i])
    for respect_ix in [4, 5, 6]:
        evaluations = []
        for i in range(len(trans["generated"])):
            inp = trans["input"][i]#0
            ret = trans["retrieved"][i]# 1
            ass = trans["assistant"][i]# 2
            pred = trans["generated"][i]# 3
            targ0 = trans["reference"][i]# 4
            targ1 = trans["line2_exact"][i]# 5
            targ2 = trans["line_contained"][i]# 6
            if SUB:
                crr = sub_evaluate_txt([inp, ret, ass, pred, targ0, targ1, targ2], respect_ix=respect_ix)
            else:
                crr = cross_evaluate_txt([inp, ret, ass, pred, targ0, targ1, targ2], respect_ix=respect_ix)
            evaluations.append(crr)
        aspects[LABELS[respect_ix]] = evaluations
    return aspects


def grounded_information_SOLO_sample_wise(evaluations, trans, ONLY_GROUNDED=True, AVOID_LEAKED=True):
    evs = {}
    for k in evaluations:
        evs[k] = {}
        #for e in evaluations[k]:
        for i in range(len(trans[k])):
            e = evaluations[k][i]
            passed = [0, 0, 0]
            sumlen = len(e)
            passed_lls = [0, 0, 0]
            sum_lls = 0
            #for sample in e:
            for j in range(len(trans[k][i])):
                sample = e[j]
                if AVOID_LEAKED and sample[0]:
                    continue
                linelen = len(trans[k][i][j])
                sum_lls += linelen
                for ix in range(1, 4, 1):
                    if not sample[ix]:
                        if ONLY_GROUNDED:
                            break
                        else:
                            continue
                    passed[ix-1] += 1
                    passed_lls[ix-1] += linelen
            e = {"line_count":[p/sumlen for p in passed]
                , "line_lengths":[p/sum_lls for p in passed_lls]}
            for aspect in e:
                if aspect not in evs[k]:
                    evs[k][aspect] = []
                    for i in range(len(e[aspect])):
                        evs[k][aspect].append([])
                for i in range(len(e[aspect])):
                    evs[k][aspect][i].append(e[aspect][i])
                
    return evs


def grounded_information(evaluations, trans, ONLY_GROUNDED=True, AVOID_LEAKED=True):
    evs = {}
    for k in evaluations:
        passed = [0, 0, 0]
        sumlen = 0
        passed_lls = [0, 0, 0]
        sum_lls = 0
        #for e in evaluations[k]:
        for i in range(len(trans[k])):
            e = evaluations[k][i]
            sumlen += len(e)
            #for sample in e:
            for j in range(len(trans[k][i])):
                sample = e[j]
                if AVOID_LEAKED and sample[0]:
                    continue
                linelen = len(trans[k][i][j])
                sum_lls += linelen
                for ix in range(1, 4, 1):
                    if not sample[ix]:
                        if ONLY_GROUNDED:
                            break
                        else:
                            continue
                    passed[ix-1] += 1
                    passed_lls[ix-1] += linelen
        evs[k] = {"line_count":{"raw":passed
                  ,"recall":[p/sumlen for p in passed]
                  , "count":sumlen}
                  , "line_lengths":{"raw":passed_lls
                  ,"recall":[p/sum_lls for p in passed_lls]
                  , "count":sum_lls}}
    return evs

def eve_to_dict(eve):
    return {"Retrieval":eve[0], "Summarization":eve[1],  "Final output":eve[2]}


def SOLE_MAIN(inputs):
    # load data
    #res_folders = ["out/chunked_3000/20260914_150843--EXPERIMENT_results/LOGGER.json"
    #    ,"out/chunked_3000/20260914_160226--EXPERIMENT_results/LOGGER.json"]
    if type(inputs) is str:
        run_pth = inputs
    else:
        run_pth = inputs[-1]
    trans = log.transform(inputs)
    evaluations = evaluate_samples(trans, SUB=True)
    # ...
    print("cost:",str(sum(trans["usages"]))+"$\t average:",str(sum(trans["usages"])/len(trans["usages"]))+"$")
    #print(evaluations)
    print("Grounded chain")
    evs = grounded_information(evaluations=evaluations, trans=trans)
    for k in evs:
        print(k+":")
        for l in evs[k]:
            print(evs[k])

    print("Correct ALL")
    evs2 = grounded_information(evaluations=evaluations, trans=trans, ONLY_GROUNDED=False)
    for k in evs2:
        print(k+":")
        for l in evs2[k]:
            print(evs2[k][l])

    
    dest = Path(run_pth).parent.absolute()
    dest = str(dest)
    dest += "/" if dest[-1] != "/" else ""
    dest2 = dest+"radar/"
    os.makedirs(dest2, exist_ok=True)
    KEY = "line_count"
    KEY2 = 'line_lengths'
    pr.plot_radar(dict_a=eve_to_dict(evs["reference"][KEY]['recall']), dict_b=None, label_b=None, label_a="Agent's components", title="Recall of agent's components (reference RCA - with respect to line count)", dest=dest2)
    pr.plot_radar(dict_a=eve_to_dict(evs["reference"][KEY]['recall']), dict_b=eve_to_dict(evs["reference"][KEY2]['recall']), label_a="Line count", label_b="Line length", title="Recall of agent's components - line count vs. line length", dest=dest2)
    pr.plot_radar(dict_a=eve_to_dict(evs["reference"][KEY]['recall']), dict_b=eve_to_dict(evs["line2_exact"][KEY]['recall']), label_a="Reference RCA", label_b="Grounded log lines from reference RCA", title="Recall of agent's components - absolute performance vs. grounded", dest=dest2)
    pr.plot_radar(dict_a=eve_to_dict(evs["reference"][KEY]['recall']), dict_b=eve_to_dict(evs2["reference"][KEY]['recall']), label_a="Grounded correct information", label_b="Any correct information", title="Recall of agent's components - any correct vs. grounded only", dest=dest2)

    print("Grounded chain of equals")
    evaluations2 = evaluate_samples(trans, SUB=False)
    evs3 = grounded_information(evaluations=evaluations2, trans=trans)
    for k in evs3:
        print(k+":")
        for l in evs3[k]:
            print(evs3[k][l])
    pr.plot_radar(dict_a=eve_to_dict(evs["reference"][KEY]['recall']), dict_b=eve_to_dict(evs3["reference"][KEY]['recall']), label_a="Line contained", label_b="Line equaled", title="Recall of agent's components - contained vs. equaled", dest=dest2)

    dest2 = dest+"pcp/"
    os.makedirs(dest2, exist_ok=True)
    dest3 = dest+"hist/"
    os.makedirs(dest3, exist_ok=True)
    evs_samplewise = grounded_information_SOLO_sample_wise(evaluations=evaluations, trans=trans, ONLY_GROUNDED=True)
    for k in evs_samplewise:# TARGETS
        for Aspect in [KEY, KEY2]:
            sep = eve_to_dict(evs_samplewise[k][Aspect])
            for l in sep:# COMPONENT
                values = sep[l]
                pr.plot_hist(values=values, title="Recall ("+k+" "+Aspect+") of the "+l+" - histogram", dest=dest3)    
            pcp(sep, title="Parallel coordinates plot - recall ("+k+" - "+Aspect+")", dest=dest2)
    for TARGET_KEY in ["reference", "line2_exact", "line_contained"]:
        for rouge_tag in ["rougeL", "rouge1", "rouge2"]:
            print("Rouge ",TARGET_KEY, rouge_tag)
            for cts, ats, pts, tag in log.rouge(trans, dest2, rouge_tag=rouge_tag, TARGET_KEY=TARGET_KEY):
                pcp({"Retrieval":cts, "Summarization":ats, "Final output":pts}, title="R"+rouge_tag[1:]+" "+TARGET_KEY+" "+tag+" of agent's components ("+k+")", dest=dest2)
        

def pcp(a, title, dest, normalize=False):
    if not a:
        raise ValueError("Input dictionary is empty.")
    axes = list(a.keys())
    values = list(a.values())
    n_points = len(values[0])
    if any(len(v) != n_points for v in values):
        raise ValueError("All dictionary values must have the same length.")
    # Convert dict-of-lists into list-of-lines
    lines = []
    for i in range(n_points):
        line = [a[axis][i] for axis in axes]
        lines.append(line)
    # Normalize each axis independently, if requested
    if normalize:
        normalized = []
        for axis in axes:
            col = a[axis]
            min_v = min(col)
            max_v = max(col)
            if min_v == max_v:
                normalized.append([0.5 for _ in col])
            else:
                normalized.append([
                    (x - min_v) / (max_v - min_v)
                    for x in col
                ])
        lines = []
        for i in range(n_points):
            line = [normalized[j][i] for j in range(len(axes))]
            lines.append(line)
    x_positions = list(range(len(axes)))
    lines = np.asarray(lines)
    plt.figure(figsize=(8, 5))
    lines = np.asarray(lines)
    # Individual samples
    for line in lines:
        plt.plot(
            x_positions,
            line,
            color='black',
            alpha=0.40,
            linewidth=0.8
        )
    # Median
    median = np.median(lines, axis=0)
    plt.plot(
        x_positions,
        median,
        marker="o",
        color='red',
        linewidth=2.5,
        label="Median"
    )
    plt.xticks(x_positions, axes)
    plt.title(title)
    plt.ylabel("Normalized value" if normalize else "Raw value")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    if dest:
        safe_title = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
        plt.savefig(dest + safe_title + ".pdf", bbox_inches="tight")
        print("saved to", dest)
    else:
        plt.show()
    plt.close()

def grounded_sample(e, data, AVOID_LEAKED, ONLY_GROUNDED):
    passed = [0, 0, 0]
    passed_lls = [0, 0, 0]
    sum_lls = 0
    for j in range(len(data)):# For each Row
        sample = e[j]
        if AVOID_LEAKED and sample[0]:
            continue
        linelen = len(data[j])
        sum_lls += linelen
        for ix in range(1, 4, 1):
            if not sample[ix]:
                if ONLY_GROUNDED:
                    break
                else:
                    continue
            passed[ix-1] += 1
            passed_lls[ix-1] += linelen
    return passed, passed_lls, sum_lls

CRIT_BOTH=0
CRIT_PLEN=1
CRIT_PCNT=2
def grounded_information_sample_wise(evaluations1, evaluations2, trans, ONLY_GROUNDED=True, AVOID_LEAKED=True, CRITERIUM=CRIT_BOTH):
    evs = {}
    for k in evaluations1:#                              Evaluation
        passed = []
        sumlen = 0
        passed_lls = []
        #sum_lls = 0
        for i in range(len(trans[k])):# For each         Sample
            e1 = evaluations1[k][i]
            e2 = evaluations2[k][i]
            if  len(e1) != len(e2):
                print("SAMPLES NOT COMPARABLE???", len(e1), len(e2))
            sumlen += len(e1)
            # component-wise hits
            passed_sample1, passed_lls_sample1, sum_lls1 = grounded_sample(e1, trans[k][i], AVOID_LEAKED, ONLY_GROUNDED)
            passed_sample2, passed_lls_sample2, _ = grounded_sample(e2, trans[k][i], AVOID_LEAKED, ONLY_GROUNDED)
            passed_samples_diff = [passed_sample2[ix] - passed_sample1[ix] for ix in range(len(passed_sample1))]
            passed.append(passed_samples_diff)
            passed_lls_samples_diff = [passed_lls_sample2[ix] - passed_lls_sample1[ix] for ix in range(len(passed_lls_sample1))]
            passed_lls.append(passed_lls_samples_diff)
            #sum_lls += sum_lls1
        improvements = [0, 0, 0]
        disprovements = [0, 0, 0]
        tradeoffs = [0, 0, 0]
        for i in range(len(trans[k])):
            for j in range(3):
                if CRITERIUM == CRIT_BOTH:
                    if passed[i][j] > 0 and passed_lls[i][j] > 0:
                        improvements[j] += 1
                    elif passed[i][j] < 0 and passed_lls[i][j] < 0:
                        disprovements[j] += 1
                    else:
                        tradeoffs[j] += 1
                elif CRITERIUM == CRIT_PLEN:
                    if passed_lls[i][j] > 0:
                        improvements[j] += 1
                    elif passed_lls[i][j] < 0:
                        disprovements[j] += 1
                    else:
                        tradeoffs[j] += 1
                else:# CRITERIUM == CRIT_PCNT
                    if passed[i][j] > 0:
                        improvements[j] += 1
                    elif passed[i][j] < 0:
                        disprovements[j] += 1
                    else:
                        tradeoffs[j] += 1
        evs[k] = {"improvements":improvements
                  ,"declines":disprovements
                  ,"tradeoffs":tradeoffs}
    return evs


def another_one():
    pth_before = ["out/chunked_3000/20260914_150843--EXPERIMENT_results/LOGGER.json"
            ,"out/chunked_3000/20260914_160226--EXPERIMENT_results/LOGGER.json"]
    trans1 = log.transform(pth_before)
    evaluations1 = evaluate_samples(trans1, SUB=True)
    
    pth_after = "out/chunked_3000/20260913_172837--EXPERIMENT_results/LOGGER.json"
    trans2 = log.transform(pth_after)
    evaluations2 = evaluate_samples(trans2, SUB=True)
    KEY = "line_count"
    evs1 = grounded_information(evaluations=evaluations1, trans=trans1)
    evs2 = grounded_information(evaluations=evaluations2, trans=trans2)
    dest = "out/chunked_3000/prompt_optimization/"
    os.makedirs(dest, exist_ok=True)
    pr.plot_radar(dict_a=eve_to_dict(evs1["reference"][KEY]['recall']), dict_b=eve_to_dict(evs2["reference"][KEY]['recall']), label_a="Before prompt optimization", label_b="After prompt optimization", title="Recall of agent's components - prompt optimization", dest=dest)

    for cix in range(3):
        evs_diffs = grounded_information_sample_wise(evaluations1=evaluations1
                                        , evaluations2=evaluations2
                                        , trans=trans1
                                        , CRITERIUM=cix)
        for k in evs_diffs:
            bar_diffs_viz(dest, data=evs_diffs[k], tag=k+" "+["both", "length", "count"][cix]+" - ref. RCA")

def bar_diffs_viz(dest, data, tag):
    # Each position becomes one bar
    x = np.arange(len(data["improvements"]))
    improvements = np.array(data["improvements"])
    declines = np.array(data["declines"])
    tradeoffs = np.array(data["tradeoffs"])
    fig, ax = plt.subplots(figsize=(7, 6))
    # Stacked bars
    ax.bar(x, declines, label="Worsened", color="#E53935")
    ax.bar(x, tradeoffs, bottom=declines, label="Unchanged", color="#9E9E9E")
    ax.bar(x, improvements, bottom=declines + tradeoffs, label="Improved", color="#4CAF50")
    # Numbers
    for i in range(len(x)):
        ax.text(
            x[i],
            declines[i] / 2,
            str(declines[i]),
            ha="center",
            va="center"
        )
        ax.text(
            x[i],
            declines[i] + tradeoffs[i] / 2,
            str(tradeoffs[i]),
            ha="center",
            va="center"
        )
        ax.text(
            x[i],
            tradeoffs[i] + declines[i] + improvements[i] / 2,
            str(improvements[i]),
            ha="center",
            va="center"
        )
    # Labels
    ax.set_xticks(x)
    ax.set_xticklabels(["Retrieval", "Summarization", "Final output"])
    ax.set_ylabel("Count")
    ax.set_xlabel("Component")
    ax.set_title("Prompt optimization impact sample-wise ("+tag+")")
    ax.legend()
    plt.tight_layout()
    plt.savefig(dest+tag+"diffs.pdf")
    # plt.show()


import argparse
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--root", type=str, required=False, default="./")
    parser.add_argument(
        "-i",
        "--inputs",
        nargs="+",
        help="Validation result directories to process"
    )
    parser.add_argument("-l", "--sole", action='store_true')
    parser.add_argument("-c", "--comparison", action='store_true')

    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    global rut
    rut = args.root
    if args.sole:
        SOLE_MAIN(args.inputs)
    if args.comparison:
        another_one()
    
if __name__ == "__main__":
    main()
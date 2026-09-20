# -*- coding: utf-8 -*-

"""

Created on Thu May 14 01:11:01 2026



@author: chodo

"""

from datetime import datetime

import json

import os

LOGGER="LOGGER.json"

import matplotlib.pyplot as plt

import re

import numpy as np
import sys


import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from scipy.stats import gaussian_kde
import re


def plot_pcp(lines, axes, title, dest=None, normalize=False):
    lines = np.asarray(lines, dtype=float)
    x_positions = np.arange(len(axes))
    fig, ax = plt.subplots(figsize=(8, 5))
    # ---------------------------------------------------------
    # Calculate density for every point on every axis
    # ---------------------------------------------------------
    densities = np.zeros_like(lines)
    for j in range(lines.shape[1]):
        values = lines[:, j]
        # KDE needs some variation
        if np.std(values) > 1e-12:
            kde = gaussian_kde(values)

            densities[:, j] = kde(values)
        else:
            densities[:, j] = 1.0
    # Normalize density to 0..1
    densities -= densities.min()
    if densities.max() > 0:
        densities /= densities.max()
    # ---------------------------------------------------------
    # Plot individual trajectories
    # ---------------------------------------------------------
    cmap = plt.cm.plasma
    for i, line in enumerate(lines):
        # Average density of the points making up this trajectory
        density = np.mean(densities[i])
        # Map density to color
        color = cmap(0.15 + 0.75 * density)
        # Dense = stronger / thicker
        linewidth = 0.7 + 2.0 * density

        ax.plot(
            x_positions,
            line,
            color=color,
            linewidth=linewidth,
            alpha=0.55 + 0.4 * density
        )
    # ---------------------------------------------------------
    # Mean trajectory
    # ---------------------------------------------------------
    mean_line = np.mean(lines, axis=0)
    ax.plot(
        x_positions,
        mean_line,
        color="black",
        linewidth=3,
        marker="o",
        markersize=5,
        label="Mean"
    )
    # ---------------------------------------------------------
    # Axes / formatting
    # ---------------------------------------------------------
    ax.set_xticks(x_positions)
    ax.set_xticklabels(axes)
    ax.set_title(title)
    if normalize:
        ax.set_ylabel("Normalized value")
    else:
        ax.set_ylabel("Raw value")
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    if dest:
        safe_title = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            title
        ).strip("_")
        plt.savefig(
            dest + safe_title + ".pdf",
            bbox_inches="tight"
        )
        print("saved to", dest)
    else:
        plt.show()
    plt.close()

def pcp(a: dict, title: str = "Parallel Coordinates Plot", normalize: bool = True, dest=None):

    """

    Parallel Coordinates Plot from a dictionary.



    Example input:

        {

            "A": [1, 2],

            "B": [0, 3],

            "C": [5, 1]

        }



    Each key is one axis.

    Each list contains values for individual observations.

    """



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
    plot_pcp(lines=lines, axes=x_positions, title=title, dest=dest, normalize=normalize)

def assistant_msgs(conversation):

    msgs = []

    for msg in conversation:

        role = msg["role"]

        if role == "assistant":

            cont = msg["content"]

            if cont and type(cont) == str and len(cont) > 4:

                msgs.append(cont)

    return msgs



class logger:

    def __init__(self, dest, tag):

        self.res_folder = dest+datetime.now().strftime("%Y%m%d_%H%M%S")+"-"+tag.split(".")[0]+"/"

        os.makedirs(self.res_folder, exist_ok=True)

        self.resname = self.res_folder + LOGGER

        print(self.resname)

        self.samples = []

    

    def log(self, incident, rca, retrieved, conversation, usages):

        ret_lines = []

        for content in retrieved:

            content = content['content_json']

            for line in content:
                ret_lines.append(line)# top 15
                #ret_lines.append(content[-1])# What?

        sample = {"incident id": incident.__str__()

            , "reference":incident.get_target()# f

            , "generated":rca# F

            , "retrieved":ret_lines# R

            , "assistant": assistant_msgs(conversation=conversation)# S
            
            # let's now add also the grounded informations:
            , "input":incident.description# i
            , "line2_exact": incident.line2_exact
            , "line_contained": incident.line_contained
            , "usages":usages
            }

        self.samples.append(sample)

        with open(self.resname, "w") as fp:

            json.dump(obj=self.samples, fp=fp)



def prep(txt):

    lines = []
    if type(txt) is str:
        txt = txt.split("\n")
    
    for line in txt:
        
        if "<time>" in line:
            line = line.split("<time>")[-1]
        else:
            line = re.sub(
                r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2}',
                '<time>',
                line
            )
            line = line.split("<time>")[-1]
        line = line.strip()
        line = re.sub(r'^-+\s*', '', line)

        if len(line) == 0 or line=="```":
            continue
        lines.append(line)
    return lines



def cov_PT(targ_l, pred_l):

    cov = 0

    cnt = 0

    for tar in targ_l:

        mxcov = 0

        for pre in pred_l:

            if pre in tar:

                mxcov = max(mxcov, len(pre))

        if mxcov > 0:

            cnt += 1

        cov += mxcov

    return cov, cnt



from rouge_score import rouge_scorer

def rouge_text(pred, targ, rouge_tag="rougeL"):

    pred = "\n".join(line for line  in prep(pred))

    targ = "\n".join(line for line  in prep(targ))

    scorer = rouge_scorer.RougeScorer(

        [rouge_tag],#"rouge1", "rouge2", 

        use_stemmer=True

    )

    scores = scorer.score(targ, pred)

    return scores



def evaluate_txt(pred, targ):

    pred_l = prep(pred)

    targ_l = prep(targ)

    tl = sum([len(t) for t in targ_l])

    pl = sum([len(p) for p in pred_l])

    cv, cnt = cov_PT(targ_l=targ_l, pred_l = pred_l)

    #print("cov", cv, str(cv/tl)[:5], tl, pl)
    # return 
    return [cv, cv/tl, cv/pl, cnt, cnt/len(targ_l), cnt/len(pred_l)]


IX_cnt_rec = 4

IX_cnt_prec = 5

IX_sum_rec = 1

IX_sum_prec = 2



def zero_port(arr):

    zeros = 0

    for a in arr:

        if a == 0:

            zeros+=1

    return zeros


def evaluate_samples(trans, ix, TARGET_KEY):
    cts = []

    ats = []

    pts = []

    for i in range(len(trans["generated"])):

        pred = trans["generated"][i]

        targ = trans[TARGET_KEY][i]

        ret = trans["retrieved"][i]

        ass = trans["assistant"][i]

        crr = evaluate_txt(ret, targ)

        arr = evaluate_txt(ass, targ)

        prr = evaluate_txt(pred, targ)

        #print("---")

        cts.append(crr[ix])

        ats.append(arr[ix])

        pts.append(prr[ix])
    return cts, ats, pts

import statistics

def eva(trans, dest, ix, tag, TARGET_KEY="reference"):
    
    cts, ats, pts = evaluate_samples(trans, ix, TARGET_KEY)
    #pcp({"Retriever":cts, "Summaries":ats, "Final output":pts})
    print("retriever ", zero_port(cts))
    print("assistant ", zero_port(ats))
    print("model ", zero_port(pts))
    pcp({"Retriever":cts, "Summaries":ats, "Final output":pts}
        , normalize=False
        , title=tag+"of agent's components", dest=dest)
    #pcp({"Retriever":[1 if c > 0 else 0 for c in cts], "Summaries":[1 if c > 0 else 0 for c in ats], "Final output":[1 if c > 0 else 0 for c in pts]})



def rouge(trans, dest, rouge_tag="rougeL", TARGET_KEY="reference"):

    #dest = "/".join(pth.replace("\\","/").split("/")[:-1])+"/"

    ctsl = []

    atsl = []

    ptsl = []

    for i in range(len(trans["generated"])):

        targ = trans[TARGET_KEY][i]

        ret = trans["retrieved"][i]

        ass = trans["assistant"][i]

        pred = trans["generated"][i]

        rt = rouge_text(ret, targ, rouge_tag)[rouge_tag]

        at = rouge_text(ass, targ, rouge_tag)[rouge_tag]

        pt = rouge_text(pred, targ, rouge_tag)[rouge_tag]

        ctsl.append(rt)

        atsl.append(at)

        ptsl.append(pt)

    for measurement in ("precision", "recall", "F1"):

        if measurement == "precision":

            cts = [c.precision for c in ctsl]

            ats = [c.precision for c in atsl]

            pts = [c.precision for c in ptsl]

        elif measurement == "recall":

            cts = [c.recall for c in ctsl]

            ats = [c.recall for c in atsl]

            pts = [c.recall for c in ptsl]

        else:

            cts = [c.fmeasure for c in ctsl]

            ats = [c.fmeasure for c in atsl]

            pts = [c.fmeasure for c in ptsl]

        print("median scores:", statistics.median(cts)

              , statistics.median(ats)

              , statistics.median(pts))

        print("mean scores:", statistics.mean(cts)

              , statistics.mean(ats)

              , statistics.mean(pts))

        print("variation scores:", statistics.variance(cts)

              , statistics.variance(ats)

              , statistics.variance(pts))

        tag = measurement
        pcp({"Retriever":cts, "Summaries":ats, "Final output":pts}
            , normalize=False
            , title="R"+rouge_tag[1:]+" "+tag+" of agent's components - "+TARGET_KEY, dest=dest)
        yield cts, ats, pts, tag

     

    



def transform(pth):
    if type(pth) is not list:
        with open(pth, "r") as fp:
            samples = json.load(fp)
    else:
        samples = []
        for p in pth:
            with open(p, "r") as fp:
                s = json.load(fp)
                samples.extend(s)
    trans = {}

    for s in samples:

        for k in s:

            if k not in trans:

                trans[k] = []

            trans[k].append(s[k])

    retr = []
    for r in trans["retrieved"]:
        s = ""
        for l in r:
            s += l[-1]+"\n"
        retr.append(s)
    trans["retrieved"] = retr


    for K in ["assistant", "line2_exact", "line_contained"]:
        ass = []
        for a in trans[K]:
            s = ""
            for l in a:
                s += l+"\n"
            ass.append(s)
        trans[K] = ass

    usages = []
    for _usg in trans["usages"]:
        s = 0
        for u in json.loads(_usg[1]):
            s +=  u["cost"]
        usages.append(s)
    trans["usages"]=usages
    return trans



def test(pth):

    trans = transform(pth)

    aspect = ["generated", "retrieved", "reference", "assistant"]#"generated", "retrieved", "reference", "assistant"]

    for a in aspect:

        #print("\n",a+":")

        for s in ["emergency", "restart"]:

            i = 0

            j = 0

            for g in trans[a]:

                if s in g.lower():

                    i+=1

                    #print(j,i)

                j+=1

            #print(s+":",i)





rut = "./"
def main():
    case_experimemnts_gpt4omini_3000 =sys.argv[1]
    #case_experimemnts_gpt4omini_3000 = "out/chunked_3000/20260913_000629--VALIDATION_results/LOGGER.json"
    pth= rut + case_experimemnts_gpt4omini_3000
    #test(pth)
    trans = transform(pth)
    dest = "/".join(pth.replace("\\","/").split("/")[:-1])+"/"+"pcp/"
    os.makedirs(dest, exist_ok=True)
    for TARGET_KEY in ["reference", "line2_exact", "line_contained"]:
        eva(trans, dest, ix=IX_cnt_rec, tag="Recall [subline count] "+TARGET_KEY, TARGET_KEY=TARGET_KEY)
        eva(trans, dest, ix=IX_cnt_prec, tag="Precision [subline count] "+TARGET_KEY, TARGET_KEY=TARGET_KEY)
        eva(trans, dest, ix=IX_sum_rec, tag="Recall [subline length] "+TARGET_KEY, TARGET_KEY=TARGET_KEY)
        eva(trans, dest, ix=IX_sum_rec, tag="Precision [subline length] "+TARGET_KEY, TARGET_KEY=TARGET_KEY)
        rouge(trans, dest, rouge_tag="rougeL", TARGET_KEY=TARGET_KEY)


if __name__=="__main__":
    main()
    
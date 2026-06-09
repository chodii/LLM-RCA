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

    plt.figure(figsize=(8, 5))

    for line in lines:
        plt.plot(x_positions, line, marker="o", alpha=0.7)

    plt.xticks(x_positions, axes)
    plt.title(title)
    plt.grid(True, alpha=0.3)

    if normalize:
        plt.ylabel("Normalized value")
    else:
        plt.ylabel("Raw value")
    plt.tight_layout()
    if dest:
        safe_title=re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
        plt.savefig(dest+safe_title+".pdf")
        print("saved to", dest)
    else:
        plt.show()

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
    
    def log(self, incident, rca, retrieved, conversation):
        ret_lines = []
        for content in retrieved:
            content = content['content_json']
            for line in content:
                ret_lines.append(content[-1])
        sample = {"incident id": incident.__str__()
            , "reference":incident.get_target()
            , "generated":rca
            , "retrieved":ret_lines
            , "assistant": assistant_msgs(conversation=conversation)}
        self.samples.append(sample)
        with open(self.resname, "w") as fp:
            json.dump(obj=self.samples, fp=fp)

def prep(txt):
    lines = []
    for line in txt.split("\n"):
        if "<time>" in line:
            line = line.split("<time>")[-1]
        line = line.strip()
        if len(line) > 0:
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

import statistics
def eva(pth, ix, tag):
    dest = "/".join(pth.replace("\\","/").split("/")[:-1])+"/"
    trans = transform(pth)
    i = 0
    cts = []
    ats = []
    pts = []
    for i in range(len(trans["generated"])):
        pred = trans["generated"][i]
        targ = trans["reference"][i]
        ret = trans["retrieved"][i]
        ass = trans["assistant"][i]
        crr = evaluate_txt(ret, targ)
        arr = evaluate_txt(ass, targ)
        prr = evaluate_txt(pred, targ)
        #print("---")
        cts.append(crr[ix])
        ats.append(arr[ix])
        pts.append(prr[ix])
    #pcp({"Retriever":cts, "Summaries":ats, "Final output":pts})
    print("retriever ", zero_port(cts))
    print("assistant ", zero_port(ats))
    print("model ", zero_port(pts))
    pcp({"Retriever":cts, "Summaries":ats, "Final output":pts}
        , normalize=False
        , title=tag+"of agent's components", dest=dest)
    #pcp({"Retriever":[1 if c > 0 else 0 for c in cts], "Summaries":[1 if c > 0 else 0 for c in ats], "Final output":[1 if c > 0 else 0 for c in pts]})

def rouge(pth, rouge_tag="rougeL"):
    dest = "/".join(pth.replace("\\","/").split("/")[:-1])+"/"
    trans = transform(pth)
    ctsl = []
    atsl = []
    ptsl = []
    for i in range(len(trans["generated"])):
        targ = trans["reference"][i]
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
            , title="R"+rouge_tag[1:]+" "+tag+" of agent's components", dest=dest)
     
    

def transform(pth):
    with open(pth, "r") as fp:
        samples = json.load(fp)
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
    ass = []
    for a in trans["assistant"]:
        s = ""
        for l in a:
            s += l+"\n"
        ass.append(s)
    trans["assistant"] = ass
        
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


rut = r"C:\Users\chodo\Documents\Studies\Projects\Sweden\MasterThesis/"
def main():
    case1 = r"out/chunked_3000/20260514_133443--VALIDATION_results/LOGGER.json"
    case2 = r"out/chunked_3000/20260514_140816--VALIDATION_results/LOGGER.json"
    case3 = "out/chunked_3000/20260514_143143--VALIDATION_results/LOGGER.json"
    case4 = "out/chunked_3000/20260514_144503--VALIDATION_results/LOGGER.json"
    case5 = "out/chunked_3000/20260514_145814--VALIDATION_results/LOGGER.json"
    case6_12sampl = "out/chunked_3000/20260514_151732--VALIDATION_results/LOGGER.json"
    case7 = "out/chunked_3000/20260514_161422--VALIDATION_results/LOGGER.json"
    case8 = "out/chunked_3000/20260514_164025--VALIDATION_results/LOGGER.json"
    
    case9_ass = "out/chunked_3000/20260514_173251--VALIDATION_results/LOGGER.json"
    case10 = "out/chunked_3000/20260514_182535--VALIDATION_results/LOGGER.json"
    case11_gpt5_mini = "out/chunked_3000/20260514_192035--VALIDATION_results/LOGGER.json"
    
    case_experimemnts_gpt4omini_3000 = "out/chunked_3000/20260514_201646--EXPERIMENT_results/LOGGER.json"
    
    case_experimemnts_gpt4omini_3000 = "out/chunked_3000/20260514_201646--EXPERIMENT_results/LOGGER.json"
    case_experimemnts_gpt4omini_2000 = "out/chunked_2000/20260514_221326--EXPERIMENT_results/LOGGER.json"
    case_validation_gpt5_4_mini_3000 = "out/chunked_3000/20260515_005408--VALIDATION_results/LOGGER.json"
    pth= rut + case_experimemnts_gpt4omini_3000 
    #test(pth)
    eva(pth, ix=IX_cnt_rec, tag="Recall [subline count] ")
    eva(pth, ix=IX_cnt_prec, tag="Precision [subline count] ")
    eva(pth, ix=IX_sum_rec, tag="Recall [subline length] ")
    eva(pth, ix=IX_sum_rec, tag="Precision [subline length] ")
    rouge(pth, rouge_tag="rougeL")
    
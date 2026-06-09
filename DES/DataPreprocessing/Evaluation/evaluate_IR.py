# -*- coding: utf-8 -*-
"""
Created on Fri Apr 24 15:26:03 2026

@author: chodo
"""

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import IssueLoader
import statistics
import numpy as np

class ExperimentsEvaluator:
    def __init__(self):
        self.metrics = {}
        self.comparisons = []
        self.retriever_metric_comparisons = []
        self.agent_metric_comparisons = []
        
    
    def evaluate(self, incident, rca, retrieved, rounds):
        target_chunks_unique, target_chunks_all = incident.get_relevant_chunks()
        target = incident.get_target()
        potential_scores = incident.get_potential_scores()
        # Agent:
        metrics, agent_comparison_metric, _txts = eval_prec_rec(pred=rca, targ=target, potential_scores=potential_scores)
        # DB:
        ret_comparison_metric = eval_db_recall(METRICS = metrics
                        , retrieved_chunks=retrieved
                        , target_rca = target
                        , relevant_all = target_chunks_all
                        , relevant_unique = target_chunks_unique
                        , potential_scores = potential_scores)
        metrics["usage-rounds"] = rounds
        self.add_metrics(metrics)
        self.comparisons.append(_txts)
        self.retriever_metric_comparisons.append(ret_comparison_metric)
        self.agent_metric_comparisons.append(agent_comparison_metric)
    
    def add_metrics(self, metrics):
        for k in metrics:
            if k not in self.metrics:
                self.metrics[k] = []
            self.metrics[k].append(metrics[k])
    
    def get_results(self):
        results = {}
        for k in self.metrics:
            results[k] = metric_statistics(self.metrics[k])
        return results, self.metrics, self.retriever_metric_comparisons, self.agent_metric_comparisons
    
    def log_results(self, dest, res_name):
        stats, full_metrics, retriever_metric_comparisons, agent_metric_comparisons = self.get_results()
        TS = datetime.now().strftime("%Y%m%d_%H%M%S")+"-"
        with open(dest+TS+res_name, "w", encoding="utf-8") as fp:
            json.dump({"statistic":stats
                       ,"samples":full_metrics
                       , "retriever_compared_metrics":retriever_metric_comparisons
                       , "agent_compared_metrics": agent_metric_comparisons
                       , "compared":self.comparisons
                       }, fp=fp)
        

def metric_statistics(arr:list):
    return {"mean":sum(arr)/len(arr)
            , "median":statistics.median(arr)
            , "variation":np.var(arr)}


def src_cid(sample):# ?
    src = sample["source_path"]
    cid = sample["chunk_id"]
    return src, cid

def safe_len_diff(ar1, ar2):
    return safe_div(len(ar1), len(ar2))

def safe_div(n1, n2):
    return 0 if n2 == 0 else n1/n2



def db_rec(METRICS, target_rca, retrieved_chunks, potential_scores):
    TM = target_manager(target=target_rca)
    r2 = []# relevant unique
    for r in retrieved_chunks:
        lines = r["content_json"]
        for l in IssueLoader.line_in_content(content=lines):
            c2, _cn = TM.log_all_at_once(l)
            if c2 and r not in r2:
                r2.append(r)
    _res, coverages = TM.result_as_dict()
    comparison_metric = {}
    for k in coverages:
        METRICS["Reference recall ["+k+"]"] = coverages[k]
        if k in potential_scores:
            comparison_metric[k] = [coverages[k], potential_scores[k]]
    return r2, _res, comparison_metric

#^ this good
def eval_db_recall(METRICS, target_rca, retrieved_chunks, relevant_all, relevant_unique, potential_scores):
    r2, _res, comparison_metric = db_rec(METRICS, target_rca, retrieved_chunks, potential_scores=potential_scores)
    METRICS["recall relevant unique"] = safe_len_diff(r2, relevant_unique)
    METRICS["precission relevant unique"] = safe_len_diff(r2, retrieved_chunks)
    METRICS["retrieved"] = len(retrieved_chunks)
    METRICS["relevant unique"] = len(r2)
    return comparison_metric

#^ I think good
from nltk.translate.bleu_score import corpus_bleu, sentence_bleu, SmoothingFunction

from rouge_score import rouge_scorer
# REPLACE BLEU with ROGUE
def rouge_eval(pred, targ):
    scorer = rouge_scorer.RougeScorer(
            ['rouge1', 'rouge2', 'rouge3'],
            use_stemmer=True
        )
    rouge_scores = scorer.score(targ, pred)
    jsonscores = {}
    for key, value in rouge_scores.items():
        rouge_metr = {"precision":value.precision, "recall":value.recall, "F1":value.fmeasure}
        for k in rouge_metr:
            jsonscores[key+"-"+k] = rouge_metr[k]
    return jsonscores

def ref_vs_gen(reference:str, generated:str):
    ref_lines = reference.split("\n")
    generated = generated.split("\n")
    ref_len_words = 0
    ref_num_words = 0
    ref_num_lines = 0
    ret_len_words = 0
    ret_num_words = 0
    ret_num_lines = 0
    for ref in ref_lines:
        ref = ref.strip()
        if len(ref) == 0:
            continue
        ref_num_lines += 1
        rw_ref_words = ref.split(" ")
        ref_words = []
        for word in rw_ref_words:
            if len(word) > 0:
                ref_words.append(word)
                ref_len_words += len(word)
        ref_num_words += len(ref_words)
        for gen in generated:
            gen = gen.strip()
            rw_gen_words = gen.split(" ")
            for word in rw_gen_words:
                if len(word) == 0:
                    continue
                if word in ref_words:
                    new_ref = []
                    repe = 0
                    for _ref_word in ref_words:
                        if word == _ref_word:
                            repe += 1
                        else:
                            new_ref.append(_ref_word)
                    ref_words = new_ref
                    ret_num_words += repe
                    ret_len_words += len(word)*repe
            if gen in ref:
                ret_num_lines += 1
                break
    rcll_characters = ret_len_words/ref_len_words
    rcll_words = ret_num_words/ref_num_words
    rcll_lines = ret_num_lines/ref_num_lines
    
    return rcll_characters, rcll_words, rcll_lines

import re
def _over_normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("<time>", " ")
    text = re.sub(r"`\"\'", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip()

from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

def _lemmatize(txt):
    lemmatizer = WordNetLemmatizer()
    tokens = word_tokenize(txt)
    lemmatized_words = [lemmatizer.lemmatize(word) for word in tokens]
    new_words = []
    for word in lemmatized_words:
        norm_word = re.sub(r"[^A-Za-z0-9]+", "", word)
        if word in new_words or len(norm_word) == 0:
            continue
        new_words.append(word)
    return new_words

def _normlize(txt):
    new_arr = []
    lines = txt.lower().split("\n")
    for l in  lines:
        arr = l.strip().split(" ")
        for p in arr:
            p = p.strip()
            if len(p) == 0:
                continue
            new_arr.append(p)
    return new_arr

def eval_prec_rec(pred:str, targ:str, potential_scores:dict):
    #pred = _normlize(pred)
    #targ = _normlize(targ)
    over_pred = _over_normalize(pred)
    over_targ = _over_normalize(targ)
    rcll_characters, rcll_words, rcll_lines = ref_vs_gen(reference=targ, generated=pred)
    rouge_score = rouge_eval(pred, targ)
    pred = _lemmatize(over_pred)
    targ = _lemmatize(over_targ)
    #bleu_score = bleu_eval(pred, targ)
    #print(rouge_score)
    #print("evaluating",len(pred),"x",len(targ))
    rel_words_ret, rel_chars_ret = relevant_retrieved(pred=pred, targ=targ)
    recall_words = rel_words_ret/len(targ)
    precision_words = rel_words_ret/len(pred)
    
    recall_characters = rel_chars_ret/len(''.join(targ))
    precision_characters = rel_chars_ret/len(''.join(pred))
    metrics={"recall [number of words]":recall_words
            ,"precision [number of words]":precision_words
            , "recall [length of words]": recall_characters
            ,"precision [length of words]":precision_characters}
    for k in rouge_score:
        metrics[k] = rouge_score[k]
    log(over_pred, over_targ, metrics=metrics)
    potential_of_generated = {"words":rcll_words
                              , "characters":rcll_characters
                              , "sublines":rcll_lines}
    for k in potential_scores:
        potential_of_generated[k] = [potential_of_generated[k],potential_scores[k]]
    return metrics, potential_of_generated, {"reference":targ, "generated":pred}

def relevant_retrieved(pred:list, targ:list):
    rel_words = 0
    rel_chars = 0
    for p in pred:
        for t in targ:
            if p == t:
                rel_words += 1
                rel_chars += len(p)
                break
        #if p in targ:
        #    rec += 1
    return rel_words, rel_chars


def _word_len(text):
    text = text.replace("\n", " ").split(" ")
    word_len = 0
    for t in text:
        if len(t)>0:
            word_len += 1
    return word_len

import os
import json
from datetime import datetime
DEST = "out/eval/"
def log(pred, targ, metrics):
    os.makedirs(DEST, exist_ok=True)
    result_log = DEST+"e"+datetime.now().strftime("%Y%m%d_%H%M%S")+".json"
    obj = {"pred":pred, "targ":targ, "metrics":metrics}
    with open(result_log, "w", encoding="utf-8") as fp:
        json.dump(obj, fp)


class target_manager:
    def __init__(self, target:str):
        self.target = target# 100% word coverage
        self.line_target = target.split("\n")# 60% line coverage
        self.found_lines = []
        self.line_target_2 = target.split("\n")
        self.line_target_all = []
        for t in target.split("\n"):
            t = t.strip()
            #if len(_over_normalize(t)) > 5:# threshold
            #    self.line_target_all.append(t)
        self.found_lines2 = []
        # len:
        self._len_word_target = _word_len(target)
        self._len_target = len(target)
        self._len_line_target = len(self.line_target)
        # counters:
        self._counter_word = 0
        self._counter_subline = 0
    
    def log_all_at_once(self, line):
        self.log_in_line(line)
        c2 = self.log_in_line2(line)
        cn = self.log_in_line_nonrem(line)
        self.log_in_word(line)
        return c2, cn
    
    def log_in_line(self, line):
        new_line_target = []
        for i in range(len(self.line_target)):
            if self.line_target[i].strip() == line.strip():
                self.found_lines.append(self.line_target[i])
            else:
                new_line_target.append(self.line_target[i])
        self.line_target = new_line_target
    
    def log_in_line2(self, line):
        """ line: <line>
        """
        contribution = False
        new_line_target = []
        line = rem_TS_from_line(line)
        for i in range(len(self.line_target_2)):
            if line in self.line_target_2[i]:
                self.found_lines2.append(line)
                contribution = True
            else:
                new_line_target.append(self.line_target_2[i])
        self.line_target_2 = new_line_target
        return contribution
    
    def log_in_line_nonrem(self, line):
        line = line.strip()
        #if len(_over_normalize(line)) < 5:
        #    return False
        line = rem_TS_from_line(line)
        for i in range(len(self.line_target_all)):
            if line in self.line_target_all[i]:
                return True
        return False
    
    def log_in_word(self, line):
        for word in line.split(" "):
            self.target = self.target.replace(" "+word+" ", "")# sole words
    
    
    def result(self):
        diff_target = self._len_target - len(self.target)
        new_len_line_target = len(self.found_lines)
        new_len_line_target_2 = len(self.found_lines2)
        new_words_found = self._len_word_target - _word_len(self.target)
        return self._len_target, diff_target, self._len_word_target, new_words_found, self._len_line_target, new_len_line_target, new_len_line_target_2
    
    def result_as_dict(self):
        TM_len_target, diff_target, TM_len_word_target, TM_new_words_found, TM_len_line_target, TM_new_len_line_target, TM_new_len_line_target_2=self.result()
        results = {
                "reference [characters]":TM_len_target
                ,"matched [characters]":diff_target
                ,"reference [words]":TM_len_word_target
                ,"matched [words]":TM_new_words_found
                ,"reference [lines]":TM_len_line_target
                ,"matched [lines]":TM_new_len_line_target
                ,"matched as subset [lines]":TM_new_len_line_target_2
            }
        coverage = {
            "characters":    safe_div(diff_target,               TM_len_target)
            ,"words":       safe_div(TM_new_words_found,        TM_len_word_target)
            ,"lines":       safe_div(TM_new_len_line_target,    TM_len_line_target)
            ,"sublines":    safe_div(TM_new_len_line_target_2,  TM_len_line_target)
            }
        return results, coverage


ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
)
def rem_TS_from_line(line):
    cleaned = ISO_TIMESTAMP_RE.sub(" ", line)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace("<time>", "")
    return cleaned
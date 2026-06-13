# -*- coding: utf-8 -*-

"""

Created on Tue May 12 12:14:36 2026



@author: chodo

"""

import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



import IssueLoader

from Evaluation import evaluate_IR

import _dataset_walker as dw

from Visualizations import hist

import json



def coverage_analysis(old, new, tag, dest):

    covs = []

    for i in range(len(old)):

        cov = (new[i])/old[i]

        covs.append(cov)

    hist.hist_from_array_single(covs, x="Coverage of target output", y="Count", title="Potential "+tag+" coverage of target output", dest=dest)

    return covs



def subset_cov(target_manager, src):

    contained_fp = []

    contained_fp_all = []

    for fp in dw.dataset_iterator(src):

        contained = False

        contained_all = False

        for line in IssueLoader.log_file_reader(fp):

            target_manager.log_in_line(line)

            target_manager.log_in_word(line)

            if target_manager.log_in_line2(line):

                contained = True

            if target_manager.log_in_line_nonrem(line):

                contained_all = True

        if contained:

            contained_fp.append(fp)

        if contained_all:

            contained_fp_all.append(fp)

    return contained_fp, contained_fp_all



def api(incidents_json, chunking, dest, tag):

    lens_orig = []

    word_lens_orig = []

    line_lens_oring = []

    

    lens_new = []

    word_lens_new = []

    line_lnes_new = []

    line_2_lnes_new = []

    incident_relevant_files = {}

    incident_all_relevant_files = {}

    for i,incident in enumerate(IssueLoader.load_incidents(incidents_json=incidents_json

                                                           , chunk_size=chunking, OUT=dest

                                                           , ignore_cov_file=True)):

        print("\r",i, incident,end="")

        srcs = incident.chunk_folder.replace("\\","/").split("/")[:-1]

        src = ""

        for s in srcs:

            src += s+"/"

        src += tag

        target = incident.get_target()

        target_manager = evaluate_IR.target_manager(target)

        

        contained_fp, contained_fp_all = subset_cov(target_manager, src)

        

        incident_relevant_files[incident.ts] = contained_fp

        incident_all_relevant_files[incident.ts] = contained_fp_all

        old_str_len, new_str_len, old_word_len, new_word_len, old_line_len, new_line_len, new_len_line_target_2 = target_manager.result()

        lens_orig.append(old_str_len)

        word_lens_orig.append(old_word_len)

        line_lens_oring.append(old_line_len)

        lens_new.append(new_str_len)

        word_lens_new.append(new_word_len)# word contained

        line_lnes_new.append(new_line_len)# line exact

        line_2_lnes_new.append(new_len_line_target_2)# line contained

    # printing:

    os.makedirs(dest, exist_ok=True)

    hist.hist_from_array_single(lens_orig, x="Length of target output", y="Count", title="Length of target [characters]", dest=dest)

    hist.hist_from_array_single(word_lens_orig, x="Length of target output", y="Count", title="Length of target [words]", dest=dest)

    hist.hist_from_array_single(line_lens_oring, x="Length of target output", y="Count", title="Length of target [lines]", dest=dest)

    char_cov = coverage_analysis(lens_orig, lens_new, "character", dest=dest)

    word_cov = coverage_analysis(word_lens_orig, word_lens_new, "word", dest=dest)

    coverage_analysis(line_lens_oring, line_lnes_new, "line exact", dest=dest)

    l2l_cov = coverage_analysis(line_lens_oring, line_2_lnes_new, "line contained", dest=dest)

    with open(dest+"coverage_analysis.json", mode="w", encoding="utf-8") as fp:

        json.dump({"files":incident_relevant_files

                   ,"files_all":incident_all_relevant_files

                   , "coverage":

                       {"sublines":l2l_cov

                        ,"characters":char_cov

                        , "words":word_cov} }, fp)

    print("results saved into:", dest)

    
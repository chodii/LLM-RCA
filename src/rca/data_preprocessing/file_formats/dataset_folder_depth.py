# -*- coding: utf-8 -*-

"""

Created on Sat Feb 21 00:07:16 2026



@author: chodo

"""



import os

import sys

from rca.data_preprocessing.file_formats import file_filters as ff



from rca.data_preprocessing.file_formats import tree_viz



def print_tree(root_path, prefix=""):

    try:

        entries = sorted(os.listdir(root_path))

    except PermissionError:

        print(prefix + "└── [Permission Denied]")

        return



    entries_count = len(entries)

    

    hmi_runtimed = False

    hmi_runtimes = 0

    

    classif = ff.File_Filter()# show system and HW logs

    classif._update_ff(whitelist={classif.NONE:"Sys log", "txt":"HW log"})

    

    for i, entry in enumerate(entries):

        path = os.path.join(root_path, entry)

        connector = "└── " if i == entries_count - 1 else "├── "

        

        if os.path.isdir(path):

            extension = "    " if i == entries_count - 1 else "│   "

            print_tree(path, prefix + extension)

            if "hmi_runtime" in entry:

                hmi_runtimes += 1

                hmi_runtimed = True

            else:

                if hmi_runtimed == True:

                    hmi_runtimed = False

                    print(prefix + connector + "HMI_RUNTIMES ", hmi_runtimes)

                    hmi_runtimes = 0

                else:

                    print(prefix + connector + entry)

        else:

            if classif._classify(path) != classif.ERROR:

                print(prefix + connector + "\t\t" + entry)



def process_folder(working_dir, level, folders):

    working_dir_files = []

    for f in os.listdir(working_dir):

        fp = os.path.join(working_dir, f)

        if os.path.isdir(fp):

            folders.append((fp, working_dir, level + 1, False))

        elif os.path.isfile(fp):

            working_dir_files.append(f)

    return working_dir_files



def build_spec_tree(root):

    folder_types = {

             "dmi/hmi":{"debug", "dmesg", "lastlog", "messages", "syslog"}

            ,"sys" :{"alarm", "cli", "messages", "snmpd"}#"quagga":"folder"

            ,"app":{"hmi_runtime"}# 514 MB = 57.56 %  of the dataset and are all ".log"; others ".log" are only 10.6%

            ,"kernel":{"debug", "dmesg","syslog"}

            ,"tpws":{"TPWSError"}

            ,"bin":{".bin"}# 28.67 %

        }

    #(NOT "hmi_runtime") AND (NOT kind:folder) AND ".log" AND (NOT ext:".txt")

    #8 + 2 + 2 + 1 + 784 + 862 + 413

    # pseudo code:

    tree = {}

    folders = [(root, None, 0, False)]

    while(len(folders) > 0):

        # process in DFS

        working_dir, predecessor, level, finished = folders.pop(-1)

        if not finished:

            folders.append((working_dir, predecessor, level, True))

            working_dir_files = process_folder(working_dir, level, folders)

            working_dir_classes = classify_folder(working_dir_files, folder_types)

            if level not in tree:

                tree[level] = {}

            tree[level][working_dir] = working_dir_classes

        else:

            if level == 0:

                continue

            for c in tree[level][working_dir]:

                tree[level-1][predecessor].add(c)

    return tree



def classify_folder(folder_files, folder_types):

    folders_type = []

    for k in folder_types:

        is_k = True

        for l in folder_types[k]:

            has_l = False

            for ff_list in folder_files:

                if l in ff_list:

                    has_l = True

                    break

            if not has_l:

                is_k = False

                break

        if is_k:

            folders_type.append(k)

    return set(folders_type)





if __name__ == "__main__":

    if len(sys.argv) < 2:

        print("Usage: python tree.py <root_directory>")

        sys.exit(1)

    

    root = sys.argv[1]

    print(root)

    

    if len(sys.argv) < 3:

        print_tree(root)

        exit(0)

    

    tree_depth = int(sys.argv[2])

    print("\n" + 32*"=" + "\n" + "="*4 + " Shortened tree\n" +32*"=")

    tree = build_spec_tree(root)

    for level in range(tree_depth):

        print(str(level)+":")

        print(tree[level])

        print("\n", "-"*16)

    tree_cut = {}

    for i in range(tree_depth):

        tree_cut[i] = tree[i]

    

    tree_viz.write_tree_dot(tree_cut, "tree.dot")
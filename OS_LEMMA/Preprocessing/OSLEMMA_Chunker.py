# -*- coding: utf-8 -*-
"""
Created on Mon Mar 30 15:24:32 2026

@author: chodo
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from DataPreprocessing import _dataset_walker as walker
import log_chunker, csv_chunker


class LEMMA_chunker:
    NONE_KEY = ""
    def __init__(self, root, dest, flatten_dataset
                 , ignore_extensions=
                     [
                     #"gz"# not seen
                      #"<none>"# recognized
                     #,"csv",# not as recognized
                     "jtl"
                     ,"js"
                     ,"pptx"
                     ,"svg"
                     ,"css"
                     ,"ttf"
                     ,"map"
                     ,"md"
                     ,"html"
                     ,"woff"
                     ,"otf"
                     ,"eot"
                     ,"less"
                     ,"scss"
                     ,"txt"
                     ,"woff2"
                     ,"json"
                     ,"png"
                     ,"yml"]):
        self.root = root
        self.dest = dest
        self.flatten_dataset = flatten_dataset
        self.ignore_extensions=ignore_extensions
        
        self.files_created = set()
    
    def chunk_log(self, fp, root, nick):
        stats = log_chunker.process_log_file(fp
                                     , nick
                                     , root
                                     , dest_root=self.dest
                                     , files_created=self.files_created)
        chunk_sizes = stats["chunk_sizes"]
        return chunk_sizes
        
    def chunk_csv(self, fp, root, nick):
        chunk_sizes = csv_chunker.process_csv_file(fp=fp
                                     , nick=nick
                                     , src_root=root
                                     , dest_root=self.dest
                                     , files_created=self.files_created)
        return chunk_sizes
    
    def chunk(self, fp):
        if self.flatten_dataset:
            root = os.path.dirname(fp)
            nick = root.replace("\\","/").split("/")[-1].replace(".","")
        else:
            root = self.root
            nick = ""
        exts = walker.parse_suffixes(fp)
        if "csv" in exts or "jtl" in exts:
            self.chunk_csv(fp, root, nick)
            print("csv:", fp)
            return
        if None in exts or ("gz" in exts and len(exts) == 1):
            self.chunk_log(fp, root, nick)
            print("log:", fp)
            return
        print("skip:", fp)
    
def chunk_dataset(src, dest):
    #max_chunk_len=None#unused
    chunk_sizes = []
    print("Chunking from",src,"into",dest)
    os.makedirs(dest, exist_ok=True)
    chunkie = LEMMA_chunker(root=src, dest=dest, flatten_dataset=True)
    for fp in walker.dataset_iterator(src):
        chunkie.chunk(fp)
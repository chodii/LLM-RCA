# -*- coding: utf-8 -*-
"""
Created on Sun Mar 22 14:21:28 2026

@author: chodo
"""
KEY_META="metadata"
KEY_SRC_PTH="source"
KEY_CHUNK_ID="chunk_id"
KEY_CONTENT="content"

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import _dataset_walker as walker

import json
from Chunking import deduplicator
def line_len(line):
    if type(line) == list:
        lineparts_len = 0
        for p in line:
            lineparts_len += len(str(p))
        return lineparts_len
    else:
        print(type(line), " could not be measured")

def chunk_id(filename, chunks_created):
    if filename not in chunks_created:
        chunks_created[filename] = 0
    else:
        chunks_created[filename] += 1
    return chunks_created[filename]
    
def create_chunk(orig_filename, chunks_created, content):
    chid = chunk_id(orig_filename, chunks_created)
    
    FILE_AS_JSON = {
            KEY_SRC_PTH : orig_filename 
            , KEY_CHUNK_ID: chid
            , KEY_CONTENT : content
        }
    return FILE_AS_JSON

def write_chunk(dest_fp, files_created, chunk):
    filename = walker.unique_name(dest_fp, files_created, POST_COUNT=True)
    with open(filename+".json", mode="w", encoding="utf-8") as jfp:
        json.dump(chunk, jfp)

def get_overhead(line):
    overhead = 0
    overheadJSON = None
    if len(line) == 2:
        overhead = len(str(line[0]))
        overheadJSON = [line[0]]
    else:
        overhead = len(str(line[0]) + str(line[1]) + str(line[2]))
        overheadJSON = line[0:3]
    return overhead, overheadJSON

def my_chunk(line, new_content, max_chunk_len):
    overhead, overheadJSON = get_overhead(line)
    max_without_ts = max_chunk_len - overhead
    cont_len = len(line[-1])
    sub_chunks = int(cont_len/max_without_ts) + (1 if cont_len%max_without_ts != 0 else 0)
    for i in range(sub_chunks-1):
        line_chunk = line[-1][max_without_ts*i : max_without_ts*(i+1)]
        new_content.append(overheadJSON+[line_chunk])
    line_chunk = line[-1][max_without_ts*(sub_chunks-1):]
    new_content.append(overheadJSON+[line_chunk])

from langchain_text_splitters import RecursiveCharacterTextSplitter
def lang_chunk_RCTS(line, new_content, max_chunk_len):
    overhead, overheadJSON = get_overhead(line)
    max_without_ts = max_chunk_len - overhead
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=max_without_ts
                                                   , chunk_overlap=10
                                                   , separators=["\n\n", "\n", "\t", " ", ""])
    splits = text_splitter.split_text(line[-1])
    for s in splits:
        new_content.append(overheadJSON+[s])

from enum import Enum
class Chunking(Enum):
    SIMPLE = 0
    LANGCHAIN_RCTS = 1

def limit_content(content, max_chunk_len, CHUNKER):
    new_content = []
    for line in content:
        if len(str(line)) <= max_chunk_len:
            new_content.append(line)
            continue
        if CHUNKER == Chunking.SIMPLE:
            my_chunk(line=line, new_content=new_content, max_chunk_len=max_chunk_len)
            continue
        if CHUNKER == Chunking.LANGCHAIN_RCTS:
            lang_chunk_RCTS(line=line, new_content=new_content, max_chunk_len=max_chunk_len)
            continue
        raise Exception("Error: no chunking strategy selected.")
    return new_content

def chunk_dataset(src, dest, max_chunk_len, LIMIT_CONTENT, CHUNKING=Chunking.LANGCHAIN_RCTS):
    files_created={}
    chunks_ids={}
    chunk_sizes = []
    #print("Chunking from",src,"into",dest, end="\t ")
    os.makedirs(dest, exist_ok=True)
    llines_orig = []
    llines_dedu = []
    for fp in walker.dataset_iterator(src):
        if ".json" not in fp:
            continue
        with open(fp, mode="r", encoding="utf-8") as jfp:
            FILE_AS_JSON = json.load(jfp)
        content = []
        chunk_len = 0
        # src:
        orig_filename = FILE_AS_JSON[KEY_SRC_PTH]# root-independent
        src_dir = os.path.dirname(fp)
        # dest:        
        file_name = fp.replace(src_dir,"").replace(".", "").replace("json", "")
        #dest_dir = src_dir.replace(src, dest)
        dest_fp = dest + file_name
        FILE_AS_JSON[KEY_CONTENT], (orig_lines, dedup_lines) = deduplicator.dedupt_row(FILE_AS_JSON[KEY_CONTENT])
        llines_orig.append(orig_lines)
        llines_dedu.append(dedup_lines)
        if LIMIT_CONTENT:
            JSON_CONTENT = limit_content(FILE_AS_JSON[KEY_CONTENT], max_chunk_len, CHUNKING)
        else:
            JSON_CONTENT = FILE_AS_JSON[KEY_CONTENT]
        for line in JSON_CONTENT:
            ll = line_len(line)
            next_chun_len = chunk_len + ll
            if next_chun_len <= max_chunk_len:# add to content
                chunk_len = next_chun_len
                content.append(line)
                continue# else:
            
            if chunk_len == 0:# it is what it is, it can not be shorter
                chunk_len = ll
                content = [line]
                
                chunk = create_chunk(orig_filename, chunks_ids, content)
                write_chunk(dest_fp, files_created, chunk)
                chunk_sizes.append(chunk_len)
                
                content=[]
                chunk_len=0
            else:# there is already some content, write the chunk
                chunk = create_chunk(orig_filename, chunks_ids, content)
                write_chunk(dest_fp, files_created, chunk)
                chunk_sizes.append(chunk_len)
                
                chunk_len = ll
                content = [line]
        # last chunk:
        chunk = create_chunk(orig_filename, chunks_ids, content)
        write_chunk(dest_fp, files_created, chunk)
        chunk_sizes.append(chunk_len)
    #print(sum([chunks_ids[k] for k in chunks_ids]), "chunks created", end="\t ")
    lines_port_after_dedu = 0 if sum(llines_orig) == 0 else sum(llines_dedu)/sum(llines_orig)
    return chunk_sizes, lines_port_after_dedu

def line_lengths(src):
    line_lengths = []
    for fp in walker.dataset_iterator(src):
        if ".json" not in fp:
            continue
        with open(fp, mode="r", encoding="utf-8") as jfp:
            FILE_AS_JSON = json.load(jfp)
        JSON_CONTENT = FILE_AS_JSON[KEY_CONTENT]
        for line in JSON_CONTENT:
            ll = line_len(line)
            line_lengths.append(ll)
    return line_lengths

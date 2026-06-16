# -*- coding: utf-8 -*-

"""

Created on Tue Apr  7 11:39:56 2026



@author: chodo

"""





import os, sys


from rca.ai_agent.agent import gpt_connector

from rca.ai_agent.agent import message_manager

from rca.ai_agent.knowledge_base import db_fetcher



from datetime import datetime, timedelta

import pytz

import logging



import argparse

import json

def parse_args():

    parser = argparse.ArgumentParser(

       description="Give me the root, I'll give you the Root Cause."

       )

    parser.add_argument(

        "-r", "--root",

        dest="root",

        type=str,

        help="Path to the root folder"

    )

    args = parser.parse_args()

    root=args.root

    return root



def _convert_time(time):

    utc=pytz.UTC

    t=utc.localize(datetime.fromisoformat(time))

    return t



def extract_params(query):

    source_path:str=None

    start_ts: str=None

    end_ts: str=None

    exact_pattern:str=None

    limit:int=1

    return source_path, start_ts, end_ts, exact_pattern, limit



class DB_Tools:

    def __init__(self):

        ...

    

    def dispatch_tool(self, call):

        tool_name = call["function"]["name"]

        args = json.loads(call["function"].get("arguments", "{}"))

    

        if tool_name == "record_selector":

            return self.record_selector(**args)

        raise ValueError(f"Unknown tool: {tool_name}")

    

    def record_selector(self

                        , source_path=None

                        , start_ts=None

                        , end_ts=None

                        , exact_pattern=None

                        , similarity_pattern=None

                        , limit=1):

        recs = db_fetcher.get_file_time_pattern(source_path

                                  , start_ts

                                  , end_ts

                                  , exact_pattern

                                  , similarity_pattern

                                  , limit)

        return [r for r in recs]

    





def run_rca(user_problem: str, tool_schemas, system_prompt_pth

            , context_manager, res_dest, model):

    displatcher = DB_Tools()

    messanger = message_manager.MessageManager(

                db_manager = displatcher

                 , system_prompt_pth = system_prompt_pth

                 , context_management_strategy = context_manager

                 #, gpt = gpt_connector.ask_open_router

                 #, model=model

                 )

    messanger.init_problem(user_problem=user_problem)

    usages = []

    while True:

        if messanger.force_end:

            break

        if messanger.about_to_end:

            tool_schemas = None# I want you to talk --> therefore no tools

        conversation = messanger.get_messages()

        log_message(conversation, res_dest=res_dest)

        usage, assistant_message = gpt_connector.ask_open_router(messages=conversation

                                             , tools=tool_schemas, model=model)

        usages.append(usage)

        messanger.add_response(assistant_message)

    return assistant_message, messanger._messages, [messanger.iteration, json.dumps(usages, default=str)], messanger.get_retrieved_from_chunks(), conversation





from pathlib import Path

CHATS_OUT = "out/last_chats/"

def api(user_problem

        , context_manager

        , model

        , tools = "DESAI-tools.json"

        , system_prompt_pth = "DESAI-prompts.json"):

    PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompt_engineering"

    tools = str(PROMPTS_DIR)+"/"+tools

    system_prompt_pth=str(PROMPTS_DIR)+"/"+system_prompt_pth

    with open(file=tools, mode="r", encoding="utf-8") as fp:

        tool_schemas = json.load(fp)

    res_dest = CHATS_OUT+datetime.now().strftime("%Y%m%d_%H%M%S")

    result_log = res_dest+".json"

    #gpt_connector.ask_open_router(messages=[{"role":...,"content":...}])

    rca, messages, usages, retrieved, _conversation = run_rca(user_problem=user_problem

                            , tool_schemas=tool_schemas

                            , system_prompt_pth=system_prompt_pth

                            , context_manager=context_manager

                            , res_dest=res_dest+"/"

                            , model=model)

    os.makedirs(CHATS_OUT,exist_ok=True)

    with open(result_log, mode="w", encoding="utf-8") as fp:

        json.dump({"messages":messages, "usages":usages}, fp, default=str)

    return rca, retrieved, usages[0], _conversation



def log_message(conversationJSON, res_dest):

    result_log = res_dest+"turn"+datetime.now().strftime("%Y%m%d_%H%M%S")+".json"

    result_log = os.path.abspath(result_log)

    os.makedirs(res_dest, exist_ok=True)

    with open(result_log, mode="w", encoding="utf-8") as fp:

        json.dump(conversationJSON, fp, default=str)


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

import time

from pathlib import Path

MAX_API_RETRIES = 3

# Rate limits (429), 5xx, timeouts: more patience (pauses up to 4 min, about
# 8 min in total) so that parallel workers do not fail incidents.
MAX_TRANSIENT_RETRIES = 8

MAX_RETRY_DELAY = 240


def retry_delay(attempt, retry_after=None):

    """Exponential backoff with jitter; the server's Retry-After wins if longer."""

    import random

    delay = (2 ** attempt) * random.uniform(0.75, 1.25)

    if retry_after is not None:

        delay = max(delay, float(retry_after))

    return min(delay, MAX_RETRY_DELAY)

DEFAULT_MAX_ITER = 30

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompt_engineering"


def resolve_prompt_path(pth):

    """Absolute/existing paths are used as given; bare names (the historical
    defaults) are resolved inside the package's prompt_engineering folder."""

    p = Path(pth)

    if p.is_absolute() or p.exists():

        return str(p.resolve())

    return str(PROMPTS_DIR / p)

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

    def __init__(self, schema=None):

        # Incident schema (cached mode) or None for the shared public.log_chunks.
        self.schema = schema

    

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

        with db_fetcher.use_schema(self.schema):

            recs = db_fetcher.get_file_time_pattern(source_path

                                  , start_ts

                                  , end_ts

                                  , exact_pattern

                                  , similarity_pattern

                                  , limit)

        return [r for r in recs]

    





def run_rca(user_problem: str, tool_schemas, system_prompt_pth

            , context_manager, res_dest, model, max_iter=DEFAULT_MAX_ITER, db_schema=None
            , provider="openrouter"):

    ask = {"openrouter": gpt_connector.ask_open_router, "openai": gpt_connector.ask_open_ai}[provider]
    displatcher = DB_Tools(schema=db_schema)

    messager = message_manager.MessageManager(

                db_manager = displatcher

                 , system_prompt_pth = system_prompt_pth

                 , context_management_strategy = context_manager

                 #, gpt = gpt_connector.ask_open_router

                 #, model=model

                 , max_iter = max_iter

                 )

    messager.init_problem(user_problem=user_problem)

    usages = []

    assistant_message = {"role": "assistant", "content": ""}

    conversation = []

    consecutive_failures = 0

    run_info = {"api_errors": [], "failed": False}

    while not messager.force_end:

        conversation = messager.get_messages()

        # Final answer and summary turns are tool-free.
        tools = None if (messager.about_to_end or messager.awaiting_summary) else tool_schemas

        log_message(conversation, res_dest=res_dest)

        try:

            usage, response = ask(messages=conversation

                                                , tools=tools, model=model)

        except gpt_connector.FatalAPIError:

            # No credits / bad key: every further call fails; stop the experiment.
            raise

        except Exception as err:

            # Undo only this turn's additions and retry the same turn.
            messager.rollback_turn()

            consecutive_failures += 1

            kind = type(err).__name__

            run_info["api_errors"].append({"iteration": messager.iteration, "type": kind, "error": str(err)[:500]})

            print("\nAPI ERROR", consecutive_failures, kind, str(err)[:500])

            if isinstance(err, gpt_connector.RequestTooLargeError):

                # The identical request cannot succeed; retrying only costs time.
                run_info["failed"] = True

                break

            transient = isinstance(err, gpt_connector.TransientAPIError)

            if consecutive_failures > (MAX_TRANSIENT_RETRIES if transient else MAX_API_RETRIES):

                run_info["failed"] = True

                break

            time.sleep(retry_delay(consecutive_failures, getattr(err, "retry_after", None)))

            continue

        consecutive_failures = 0

        usages.append(usage)

        assistant_message = response

        messager.add_response(assistant_message)

    run_info["summary_tool_call_violations"] = messager.summary_tool_call_violations

    # usages[2] (run_info) is new; Logger.transform only reads usages[1].
    return assistant_message, messager._messages, [messager.iteration, json.dumps(usages, default=str), run_info], messager.get_retrieved_from_chunks(), conversation





from pathlib import Path

CHATS_OUT = "out/last_chats/"

def api(user_problem

        , context_manager

        , model

        , tools = "DESAI-tools.json"

        , system_prompt_pth = "DESAI-prompts.json"

        , max_iter = DEFAULT_MAX_ITER

        , chats_dir = None

        , chat_id = None

        , db_schema = None
        , provider = "openrouter"):

    # Chat logs: <chats_dir>/<chat_id>/turn*.json and <chats_dir>/<chat_id>.json;
    # defaults: out/last_chats/ and a timestamp.
    chats_dir = CHATS_OUT if chats_dir is None else os.path.join(chats_dir, "")

    tools = resolve_prompt_path(tools)

    system_prompt_pth = resolve_prompt_path(system_prompt_pth)

    with open(file=tools, mode="r", encoding="utf-8") as fp:

        tool_schemas = json.load(fp)

    res_dest = chats_dir+(chat_id or datetime.now().strftime("%Y%m%d_%H%M%S"))

    result_log = res_dest+".json"

    #gpt_connector.ask_open_router(messages=[{"role":...,"content":...}])

    rca, messages, usages, retrieved, _conversation = run_rca(user_problem=user_problem

                            , tool_schemas=tool_schemas

                            , system_prompt_pth=system_prompt_pth

                            , context_manager=context_manager

                            , res_dest=res_dest+"/"

                            , model=model

                            , max_iter=max_iter

                            , db_schema=db_schema
                            , provider=provider)

    os.makedirs(chats_dir,exist_ok=True)

    with open(result_log, mode="w", encoding="utf-8") as fp:

        json.dump({"messages":messages, "usages":usages[0], "run_info":usages[2]}, fp, default=str)

    return rca, retrieved, usages, _conversation



def log_message(conversationJSON, res_dest):

    result_log = res_dest+"turn"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json"

    result_log = os.path.abspath(result_log)

    os.makedirs(res_dest, exist_ok=True)

    with open(result_log, mode="w", encoding="utf-8") as fp:

        json.dump(conversationJSON, fp, default=str)


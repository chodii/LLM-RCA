# -*- coding: utf-8 -*-

"""

Created on Fri Apr 24 17:57:27 2026



@author: chodo

"""

class MessageManager:...



def standardize(prompt):

    if type(prompt["content"]) is str:

        return prompt

    c = ""

    for k in prompt["content"]:

        c += "\n"+k

    prompt["content"] = c

    return prompt





def truncate_retrieved(manager):

    if manager.last_calls == 0:

        return

    for i in range(manager.last_calls):

        calls = manager.messages.pop()

        print("pop",calls["role"], len(calls), "-", str(calls["content"])[:200])

    message = manager.messages.pop()

    if "tool_calls" in message:

        message.pop("tool_calls")# remove all tool calls

    manager.messages.append(message)# keep at least track of thoughts

    print("popop", len(manager.messages))







def default_composer(manager):

    messages = []

    for ix in manager._msg_ix_crucial:

        messages.append(manager._messages[ix])

    return messages



SUMMARIZATION_KEY = "summarization"

def summarize(manager:MessageManager):

    messages = default_composer(manager)

    if len(manager._last_calls) == 0:# no tool calls, chill

        #...

        # was last message important or a summary?

        return messages

    for ix in manager._last_calls:# TOOLS

        messages.append(manager._messages[ix])

    # ask for a summary:            SUMMARY REQUEST

    if manager.about_to_end:

        return messages# tools included finito

    messages.append(manager.get_prompt(SUMMARIZATION_KEY))

    return messages

    



def context_management_prompt(manager):

    ...



def foo_none(manager):

    ...# by intention - do nothing





from enum import Enum

class ContextManagement(Enum):

    TRUNCATION          = truncate_retrieved

    SUMMARIZATION       = summarize

    CONTEXT_MANAGEMENT  = context_management_prompt

    NONE  = foo_none





import json

INITIAL_MSG_KEY = "initial_prompt"

FORCE_STOP_KEY = "force_end_prompt"



KEEP_ALL_CONTENT = True

PERSERVE_REASONING = False

class MessageManager:

    _retrieved_from_chunks = []

    def __init__(self, db_manager

                 , system_prompt_pth

                 , context_management_strategy

                 #, gpt

                 #, model

                 , max_iter = 30):

        self.db_manager = db_manager

        #self.gpt = gpt# might be used, depending on the context_management_strategy

        

        self.predefined_prompts = None

        with open(system_prompt_pth, "r", encoding="utf-8") as fp:

            self.predefined_prompts = json.load(fp)

        messages = [standardize(self.predefined_prompts[INITIAL_MSG_KEY])]

        

        self.force_end = False

        self.about_to_end = False

        self.context_composer = context_management_strategy

        self._last_calls = []

        self.iteration = 0

        self.max_iter = max_iter

        self._messages = messages

        self._msg_ix_crucial = [ix for ix in range(len(messages)+1)]

        

    def init_problem(self, user_problem):

        self._messages.append({"role": "user", "content": user_problem})

        if self.context_composer is ContextManagement.TRUNCATION:

            ...

            return

        if self.context_composer is ContextManagement.SUMMARIZATION:

            ...

            return

        if self.context_composer is ContextManagement.CONTEXT_MANAGEMENT:

            ...

            return

    

    def get_prompt(self, key):

        prompt = self.predefined_prompts[key]

        self._messages.append(prompt)# keep the conversation whole

        return prompt

    

    def get_retrieved_from_chunks(self):

        return self._retrieved_from_chunks

    

    def retrieved_from_chunks(self, result):

        for record in result:

            file = record.get("source_path", None)

            cid = record.get("chunk_id", None)

            if file is None or cid is None:

                print("\nNONE SOURCE FILE OR CHUNK ID:",record)

                continue

            self._retrieved_from_chunks.append(record)

    

    def add_response(self, assistant_message):

        if self.about_to_end:

            self.force_end = True

        if assistant_message.get("refusal"):

            print("MODEL IS REFUSING TO ANSWER")

            self._messages.append(assistant_message)

            self.force_end = True

            return

        self.iteration += 1

        tool_calls = assistant_message.get("tool_calls", [])

        content = assistant_message.get("content",[])

        reasoning = assistant_message.get("reasoning",[])

        

        self._last_calls = []

        if tool_calls:

            self._last_calls.append(len(self._messages))# = the index of the next message

            self._messages.append({

                "role": "assistant",

                "content": content,

                "reasoning":reasoning,

                "tool_calls": tool_calls,

            })

            # Keep the assistant tool-call message in history

            for ix, call in enumerate(tool_calls):

                name = call.get("function",{}).get("name", None)

                if name is None:

                    print("ERROR", call)

                elif name == "record_selector":

                    result = self.db_manager.dispatch_tool(call)

                    self._last_calls.append(len(self._messages))# = the index of the next message

                    self._messages.append({

                        "role": "tool",

                        "tool_call_id": call["id"],

                        #"content": json.dumps(result),

                        "content": json.dumps(result, default=str),

                        

                    })

                    self.retrieved_from_chunks(result)

                elif name == "done":

                    self.about_to_end = True

                    self._last_calls.append(len(self._messages))

                    self._messages.append({

                        "role": "tool",

                        "tool_call_id": call["id"],

                        "content": json.dumps([], default=str),

                    })

        else:

            if KEEP_ALL_CONTENT and content is not None:

                self._msg_ix_crucial.append(len(self._messages))

            self._messages.append({

                "role": "assistant",

                "content": content,

                "reasoning":reasoning

            })

        if (not self.force_end) and (self.iteration > self.max_iter):

            # the model has stopped tool calling

            self.about_to_end = True# dynamic

            print("\n!! The model seems to be arriving to an answer !!\n")

        else:

            print("\r",self.iteration, end="")

        

    

    def get_messages(self):

        messages = self.context_composer(self)

        if (not self.force_end) and self.about_to_end:

            messages.append(self.get_prompt(FORCE_STOP_KEY))

        if PERSERVE_REASONING:

            return messages

        reasonless_messages = []

        for m in messages:

            newM = {}

            for k in m:

                if k == "reasoning":

                    continue

                newM[k]=m[k]

            reasonless_messages.append(newM)

        return reasonless_messages

"""

    def add_response(self, assistant_message):

        if assistant_message.get("refusal"):

            print("MODEL IS REFUSING TO ANSWER")

            self._messages.append(assistant_message)

            self.force_end = True

        self.iteration += 1

        tool_calls = assistant_message.get("tool_calls", [])

        role = assistant_message.get("role","")

        self.context_manager(self)

        self._last_calls = len(tool_calls)

        

        past_conclusion=None

        assistant_ready_for_conclusion=False

        #if content is None or content == []:

        content = assistant_message.get("content",[])

                    

        reasoning = assistant_message.get("reasoning",[])

        if tool_calls:

            self._messages.append({

                "role": "assistant",

                "content": content,

                "reasoning":reasoning,

                "tool_calls": tool_calls,

            })

            # Keep the assistant tool-call message in history

            for call in tool_calls:

                result = self.db_manager.dispatch_tool(call)

                self._messages.append({

                    "role": "tool",

                    "tool_call_id": call["id"],

                    #"content": json.dumps(result),

                    "content": json.dumps(result, default=str),

                })

        else:

            self._messages.append({

                "role": "assistant",

                "content": content,

                "reasoning":reasoning

            })

        if (role == "assistant" and content is not None and len(content) > 0):

            if past_conclusion is None:

                past_conclusion = content

            elif past_conclusion == content:

                assistant_ready_for_conclusion=True

        investigation_exceeding_budget = (self.iteration >= self.max_iter-1)

        print("\r",self.iteration, "-", assistant_ready_for_conclusion, investigation_exceeding_budget, end="")

        if self.about_to_end or assistant_ready_for_conclusion:

            self.force_end = True

            return

        if investigation_exceeding_budget:

            self.about_to_end = True

            self._messages.append(self.predefined_prompts[FORCE_STOP_KEY])

"""


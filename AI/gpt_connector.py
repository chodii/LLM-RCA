# -*- coding: utf-8 -*-
"""
Created on Thu Jan  1 01:31:58 2026

@author: chodo
"""

import os
from openai import OpenAI
def ask_open_ai():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "How do you say hi in swedish?"}
        ],
    )
    
    print(response.choices[0].message.content)

import requests
import json
import time
def ask_open_router(messages, tools=None, timer=0.5, model="openai/gpt-4o-mini"):
    time.sleep(timer)
    API_KEY = os.environ["OPENROUTER"]
    #model = "openai/gpt-5.2"
    model=model
    #model="openai/gpt-5-mini"
    
    #model = "xiaomi/mimo-v2.5-pro"
    #model = "xiaomi/mimo-v2.5"
    
    #model="google/gemma-4-31b-it:free"
    #model="google/gemma-4-26b-a4b-it:free"
    data_content = {
          #"model": "openai/gpt-5.2" # Optional
          #"model":"inclusionai/ling-2.6-1t:free"
          #"model":"nvidia/nemotron-3-super-120b-a12b:free"
          #"model":"openai/gpt-4o-mini"
          #"deepseek/deepseek-v4-flash"
          "model":model
          ,"messages": messages
          
        }
    if tools:
        data_content["tools"] = tools
    response = requests.post(
      url="https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": f"Bearer {API_KEY}",
        #"HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        #"X-OpenRouter-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
        
        },
      data=json.dumps(data_content)
    )
    #return response
    if not response.ok:
        print("STATUS:", response.status_code)
        print("BODY:", response.text[:5000])
        response.raise_for_status()
    response.raise_for_status()

    model_response = response.json()
    usage = model_response.get("usage", {})
    model_response = model_response["choices"][0]["message"]
    return usage, model_response
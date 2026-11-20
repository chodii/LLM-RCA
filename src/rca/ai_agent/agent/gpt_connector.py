# -*- coding: utf-8 -*-

"""

Created on Thu Jan  1 01:31:58 2026



@author: chodo

"""



import os

import requests

import json

import time

REQUEST_TIMEOUT = (30, 600)


import threading


class RequestPacer:

    """Polite client side limits shared by every thread of the process:
    at most max_in_flight requests at once, at least min_interval seconds
    between request starts, and a shared pause after the server signalled
    overload (429/5xx; Retry-After honoured) so that all workers back off."""

    def __init__(self, min_interval=1.0, max_in_flight=4):

        self._lock = threading.Lock()

        self._next_start = 0.0

        self._cooldown_until = 0.0

        self.configure(min_interval, max_in_flight)

    def configure(self, min_interval=None, max_in_flight=None):

        with self._lock:

            if min_interval is not None:

                self.min_interval = max(0.0, float(min_interval))

            if max_in_flight is not None:

                self.max_in_flight = max(1, int(max_in_flight))

                self._slots = threading.BoundedSemaphore(self.max_in_flight)

    def __enter__(self):

        slots = self._slots

        slots.acquire()

        self._held = slots

        with self._lock:

            now = time.monotonic()

            start = max(now, self._next_start, self._cooldown_until)

            self._next_start = start + self.min_interval

        if start > now:

            time.sleep(start - now)

        return self

    def __exit__(self, *exc):

        self._held.release()

        return False

    def cooldown(self, seconds):

        with self._lock:

            self._cooldown_until = max(self._cooldown_until, time.monotonic() + max(0.0, seconds))


# Defaults: ~60 requests/minute, 4 in flight; DESExperiments --workers/--max-rpm adjust them.
PACER = RequestPacer(min_interval=1.0, max_in_flight=4)

# Shared pause after a 429/5xx without Retry-After.
DEFAULT_COOLDOWN = 10.0


class APIError(Exception):
    """Base class of classified API errors."""


class TransientAPIError(APIError):
    """Rate limit (429), server error (5xx), timeout, network error or an error
    body: worth retrying, after retry_after seconds if the server said so."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class RequestTooLargeError(APIError):
    """The request cannot succeed as sent (e.g. context length exceeded)."""


class FatalAPIError(APIError):
    """Retrying is pointless for every incident: bad key (401), no credits (402),
    forbidden (403). The experiment must stop."""


def _retry_after(response):
    try:
        return max(0.0, float(response.headers.get("Retry-After")))
    except (TypeError, ValueError):
        return None


def classify_http_error(status, body, retry_after=None):
    text = (body or "")[:1000]
    if status in (401, 402, 403):
        return FatalAPIError(f"HTTP {status}: {text}")
    if status == 429 or status >= 500 or status in (408, 409):
        return TransientAPIError(f"HTTP {status}: {text}", retry_after)
    if status in (400, 413) and any(k in text.lower() for k in ("context", "too long", "too large", "maximum", "token")):
        return RequestTooLargeError(f"HTTP {status}: {text}")
    if status == 400:
        return RequestTooLargeError(f"HTTP {status} (bad request, not retried): {text}")
    return TransientAPIError(f"HTTP {status}: {text}", retry_after)

PROVIDER_KEYS = {"openrouter": "OPENROUTER", "openai": "OPENAI_API_KEY"}
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
# USD per million text tokens: input, cached input, output.
# https://developers.openai.com/api/docs/models/gpt-4o-mini
OPENAI_TEXT_RATES = {
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.075, 0.60),
}


def require_api_key(provider):
    env_var = PROVIDER_KEYS[provider]
    key = os.environ.get(env_var, "").strip()
    if not key:
        raise FatalAPIError(f"Set {env_var} to use {provider}.")
    return key


def ask_open_router(messages, tools=None, timer=0.11, model="openai/gpt-4o-mini"):
    return _ask(messages, tools, timer, model, "openrouter", _post)


def ask_open_ai(messages, tools=None, timer=0.11, model=OPENAI_DEFAULT_MODEL):
    messages = [{k: v for k, v in message.items() if k != "reasoning"} for message in messages]
    if tools:
        # The experiment schemas put strict alongside function. Chat
        # Completions expects it inside the function definition.
        tools = [
            {"type": "function", "function": dict(tool["function"], strict=tool["strict"])}
            if tool.get("type") == "function" and "strict" in tool else tool
            for tool in tools
        ]
    usage, message = _ask(messages, tools, timer, model, "openai", _post_openai)
    rates = OPENAI_TEXT_RATES.get(model)
    if rates and "prompt_tokens" in usage and "completion_tokens" in usage:
        input_rate, cache_rate, output_rate = rates
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        usage["cost"] = ((usage["prompt_tokens"] - cached) * input_rate
                         + cached * cache_rate + usage["completion_tokens"] * output_rate) / 1_000_000
    return usage, message


def _ask(messages, tools, timer, model, provider, post):
    api_key = require_api_key(provider)
    time.sleep(timer)
    data_content = {"model": model, "messages": messages}
    if tools:
        data_content["tools"] = tools

    try:

        with PACER:

            response = post(api_key, data_content)

    except requests.exceptions.RequestException as err:

        # timeouts, connection resets, DNS problems
        raise TransientAPIError(f"{type(err).__name__}: {err}") from err

    if not response.ok:
        if provider == "openai" and response.status_code == 429:
            try:
                error_body = response.json().get("error", {})
            except ValueError:
                error_body = {}
            if isinstance(error_body, dict) and error_body.get("code") == "insufficient_quota":
                raise FatalAPIError("OpenAI rejected the request due to insufficient quota.")

        print("STATUS:", response.status_code)

        print("BODY:", response.text[:5000])

        error = classify_http_error(response.status_code, response.text, _retry_after(response))

        if isinstance(error, TransientAPIError) and (response.status_code == 429 or response.status_code >= 500):

            # every worker of this process pauses, not only the one that was told
            PACER.cooldown(error.retry_after if error.retry_after is not None else DEFAULT_COOLDOWN)

        raise error

    try:

        model_response = response.json()

    except ValueError as err:

        raise TransientAPIError(f"invalid JSON from {provider}: {response.text[:300]}") from err

    usage = model_response.get("usage") or {}

    if "choices" not in model_response or not model_response["choices"]:

        # OpenRouter reports provider errors with HTTP 200 and an error object.
        error = model_response.get("error") or {}

        code = error.get("code") if isinstance(error, dict) else None

        message = f"no choices in response: {json.dumps(model_response)[:500]}"

        if isinstance(code, int) and code >= 400:

            raise classify_http_error(code, message)

        raise TransientAPIError(message)

    return usage, model_response["choices"][0]["message"]


def _post(api_key, data_content):

    return requests.post(

      url="https://openrouter.ai/api/v1/chat/completions",

      headers={

        "Authorization": f"Bearer {api_key}",

        #"HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.

        #"X-OpenRouter-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.

        

        },

      data=json.dumps(data_content)

      # (connect, read) seconds: a stalled connection becomes an error that
      # DESAI.run_rca retries instead of hanging the experiment forever.
      , timeout=REQUEST_TIMEOUT

    )


def _post_openai(api_key, data_content):
    return requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=data_content,
        timeout=REQUEST_TIMEOUT,
    )

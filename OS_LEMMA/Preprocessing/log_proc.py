# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 16:44:44 2026

@author: chodo
"""
import json

import re
import os
GLOG_RE = re.compile(
    r'^(?P<level>[IWEF])(?P<mmdd>\d{4})\s+'
    r'(?P<clock>\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+'
    r'(?P<thread>\d+)\s+'
    r'(?P<file>[^:\]]+):(?P<line>\d+)\]\s*'
    r'(?P<msg>.*)$'
)
KV_RE = re.compile(
    r'([A-Za-z0-9_.:/@-]+)=("(?:(?:\\.)|[^"])*"|[^"\s]+)'
)

METRIC_KEY_HINTS = (
    "cpu", "memory", "network", "packets", "errors", "dropped",
    "request", "limit", "usage", "working_set", "rss", "cache",
    "swap", "pgfault", "pgmajfault", "failcnt", "max_usage",
    "tx_bytes", "rx_bytes"
)


def limit_text(text: str, max_len: int = 800) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def get_nested(d, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def shorten_audit_event(obj: dict) -> str:
    user = get_nested(obj, "user", "username", default="")
    srcs = obj.get("sourceIPs") or []
    src = srcs[0] if srcs else ""
    code = get_nested(obj, "responseStatus", "code", default="")
    verb = obj.get("verb", "")
    uri = obj.get("requestURI", "")
    stage = obj.get("stage", "")
    resource = get_nested(obj, "objectRef", "resource", default="")
    namespace = get_nested(obj, "objectRef", "namespace", default="")
    name = get_nested(obj, "objectRef", "name", default="")
    group = get_nested(obj, "objectRef", "apiGroup", default="")
    return limit_text(
        f"audit verb={verb} stage={stage} code={code} user={user} src={src} "
        f"resource={resource} namespace={namespace} name={name} apiGroup={group} uri={uri}"
    )


def shorten_metrics_json(obj: dict) -> str:
    entity_parts = []

    for key in ("ClusterName", "LaunchType", "Namespace", "PodName", "Type", "NodeName"):
        if key in obj:
            entity_parts.append(f"{key}={obj[key]}")

    container = obj.get("container") or get_nested(obj, "kubernetes", "container_name")
    if container:
        entity_parts.append(f"container={container}")

    image = obj.get("image")
    if image:
        entity_parts.append(f"image={image.rsplit('/', 1)[-1]}")

    metric_parts = []
    for k, v in obj.items():
        if isinstance(v, (int, float)):
            lk = k.lower()
            if any(h in lk for h in METRIC_KEY_HINTS):
                metric_parts.append((k, v))

    metric_parts.sort(key=lambda x: x[0])

    metric_str = " ".join(f"{k}={v}" for k, v in metric_parts)
    entity_str = " ".join(entity_parts)
    return limit_text(f"metrics {entity_str} {metric_str}".strip())


def shorten_generic_json(obj: dict) -> str:
    kept = []
    for k, v in obj.items():
        if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 120:
            kept.append(f"{k}={v}")
    return limit_text("json " + " ".join(kept[:20]))


def parse_logfmt_pairs(body: str) -> dict:
    out = {}
    for m in KV_RE.finditer(body):
        k = m.group(1)
        v = m.group(2)
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            try:
                v = json.loads(v)
            except Exception:
                v = v[1:-1]
        out[k] = v
    return out

def shorten_logfmt(body: str) -> str:
    kv = parse_logfmt_pairs(body)
    if not kv:
        return limit_text(body)

    level = kv.get("level", "")
    msg = kv.get("msg", "")
    method = kv.get("method", "")
    path = kv.get("path", "")
    error = kv.get("error", "")
    client = kv.get("client", "")
    accountid = kv.get("accountid", "")
    arn = kv.get("arn", "")
    inner_time = kv.get("time", "")

    pieces = [
        "auth",
        f"time={inner_time}" if inner_time else "",
        f"level={level}" if level else "",
        f"msg={json.dumps(msg)}" if msg else "",
        f"method={method}" if method else "",
        f"path={path}" if path else "",
        f"error={json.dumps(error)}" if error else "",
        f"client={client}" if client else "",
        f"accountid={accountid}" if accountid else "",
        f"arn={arn}" if arn else "",
    ]
    return limit_text(" ".join(x for x in pieces if x))


def shorten_payload(body: str) -> str:
    body = body.strip()
    if not body:
        return ""

    if body.startswith("{") and body.endswith("}"):
        return shorten_json_payload(body)

    if "=" in body:
        return shorten_logfmt(body)

    return limit_text(body)


def shorten_json_payload(body: str) -> str:
    try:
        obj = json.loads(body)
    except Exception:
        return limit_text(body)

    if obj.get("kind") == "Event" and str(obj.get("apiVersion", "")).startswith("audit.k8s.io/"):
        return shorten_audit_event(obj)

    if "ClusterName" in obj and "PodName" in obj and "Type" in obj:
        return shorten_metrics_json(obj)

    return shorten_generic_json(obj)

def shorten_glog(body: str) -> str:
    m = GLOG_RE.match(body.strip())
    if not m:
        return limit_text(body)

    level = m.group("level")
    src_file = m.group("file")
    src_line = m.group("line")
    msg = m.group("msg").strip()

    # Drop the inner time and thread id, keep stable source + message.
    return limit_text(f"glog level={level} src={src_file}:{src_line} msg={msg}")

def shorten_payload(body: str) -> str:
    body = body.strip()
    if not body:
        return ""

    if body.startswith("{") and body.endswith("}"):
        return shorten_json_payload(body)

    if "=" in body:
        return shorten_logfmt(body)

    if GLOG_RE.match(body):
        return shorten_glog(body)

    return limit_text(body)
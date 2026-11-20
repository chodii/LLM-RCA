# -*- coding: utf-8 -*-

"""

Created on Fri Apr 24 16:00:35 2026



@author: chodo

"""



import os, sys




from rca.data_preprocessing.evaluation_set import IssueLoader

from rca.ai_agent.experiments import evaluate_IR

from rca.ai_agent.experiments import coverage_analysis

from rca.results import Logger



from rca.ai_agent.agent import DESAI

from rca.ai_agent.agent import message_manager

from rca.ai_agent.knowledge_base import db_fetcher, db_loader

import argparse

import contextlib

import hashlib

import traceback

from concurrent.futures import ThreadPoolExecutor, as_completed

import json

import shutil

import subprocess

from datetime import datetime

from pathlib import Path


def coverage_analysis_api(incidents_json, chunking):
    if chunking is None:
        tag = "windowed_selection/"
    else:
        tag = "chunked_"+str(chunking)+"/"
    dest = "out/"+tag
    coverage_analysis.api(incidents_json, chunking, dest, tag)
    



RUNNER_VERSION = "v9.17.913"

# Bump when evaluate_IR/xBinTable/Logger scoring changes.
# v2: evaluate_IR.ref_vs_gen ignores blank generated lines ("sublines" metric of
# the runner's results file); xBinTable/Logger chained recall is unchanged.
EVALUATOR_VERSION = "v2 (xBinTable chained recall unchanged; evaluate_IR sublines blank-line fix)"

REQUIRED_PROMPT_KEYS = (message_manager.INITIAL_MSG_KEY
                        , message_manager.FORCE_STOP_KEY
                        , message_manager.SUMMARIZATION_KEY)

RUN_CONFIG = "run_config.json"


class ConfigError(ValueError):
    ...


def _load_json(pth, what):
    if not os.path.isfile(pth):
        raise ConfigError(f"{what} file not found: {pth}")
    try:
        with open(pth, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except UnicodeDecodeError as err:
        raise ConfigError(f"{what} file is not valid UTF-8: {pth} ({err})")
    except json.JSONDecodeError as err:
        raise ConfigError(f"{what} file is not valid JSON: {pth} ({err})")


def validate_prompts(pth):
    prompts = _load_json(pth, "Prompt")
    if not isinstance(prompts, dict):
        raise ConfigError(f"Prompt file must be a JSON object: {pth}")
    for key in REQUIRED_PROMPT_KEYS:
        p = prompts.get(key)
        if not isinstance(p, dict):
            raise ConfigError(f"Prompt file {pth} is missing required prompt '{key}'")
        if p.get("role") not in ("system", "user"):
            raise ConfigError(f"Prompt '{key}' in {pth} needs role 'system' or 'user'")
        content = p.get("content")
        ok = isinstance(content, str) or (isinstance(content, list)
                                          and all(isinstance(c, str) for c in content))
        if not ok or not content:
            raise ConfigError(f"Prompt '{key}' in {pth} needs non-empty string (or list of strings) content")
    return prompts


def validate_tools(pth):
    tools = _load_json(pth, "Tool schema")
    names = []
    if isinstance(tools, list):
        names = [t.get("function", {}).get("name") for t in tools if isinstance(t, dict)]
    if "record_selector" not in names:
        raise ConfigError(f"Tool schema file {pth} must be a list of function tools including 'record_selector'")
    return tools


def reported_time_hint(incident_ts, enabled=True):
    """Historical (optimized-prompt) wording, kept byte-identical; it uses only
    the reported incident date, never log timestamps or the reference RCA."""
    if not enabled:
        return ""
    if incident_ts is None or str(incident_ts).strip().lower() in ("", "none", "nan", "nat"):
        return ""
    date = str(incident_ts).split("T")[0].strip()
    return "This incident occured around (yyyy-mm-dd):"+date+"\n"


def select_split(i, split):
    validation = (i % 5 == 0)
    return validation if split == "validation" else not validation


def _sha256(pth):
    with open(pth, "rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


class ExperimentLocked(RuntimeError):
    pass


EXIT_LOCKED = 3

EXIT_FATAL_API = 4


@contextlib.contextmanager
def db_lock():
    """Exclusive per-database lock: every incident swaps the shared log_chunks
    table, so two experiments on the same database would corrupt each other."""
    import fcntl
    import tempfile
    name = "".join(c if c.isalnum() else "_" for c in os.environ.get("DESAI_DBNAME", "default"))
    path = os.path.join(tempfile.gettempdir(), f"desai-experiment-{name}.lock")
    fp = open(path, "w")
    try:
        try:
            fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ExperimentLocked(f"another experiment is using database '{name}' (lock {path})")
        fp.write(str(os.getpid()))
        fp.flush()
        yield path
    finally:
        fp.close()


def git_state():
    pkg_root = str(Path(__file__).resolve().parents[4])# LLM-RCA-main/
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=pkg_root, capture_output=True
                                  , text=True, timeout=30).stdout
        except Exception as err:
            return f"unavailable: {err}"
    diff = git("diff", "HEAD", "--", pkg_root)
    return {"commit": git("rev-parse", "HEAD").strip()
            , "dirty_files": [l for l in git("status", "--porcelain", "--untracked-files=no", "--", pkg_root).splitlines() if l]
            , "diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest()}


def _write_config(res_folder, config):
    with open(os.path.join(res_folder, RUN_CONFIG), "w", encoding="utf-8") as fp:
        json.dump(config, fp, indent=2, default=str)


def api(context_manager, incidents_json, chunk_size ,model, VALIDATION=False
        , prompts_pth=DESAI.resolve_prompt_path("DESAI-prompts.json")
        , tools_pth=DESAI.resolve_prompt_path("DESAI-tools.json")
        , time_hint=True
        , max_iter=DESAI.DEFAULT_MAX_ITER
        , config_name=None
        , out_dir=None
        , repetition=1
        , allow_overwrite=False
        , settings=None
        , incident_limit=None
        , db_mode="cached"
        , workers=1
        , provider="openrouter"):
    print(RUNNER_VERSION)
    #incident=None
    #incidents_json=r".\DataPreprocessing\out\chunked_incidents.json"
    tag = "chunked_"+str(chunk_size)+"/"
    dest = "out/"+tag
    # coverage_analysis.json (reference grounding) is always read from out/chunked_<size>/
    results_dest = dest if out_dir is None else os.path.join(out_dir, "")
    split = "validation" if VALIDATION else "heldout"
    if VALIDATION:
        res_name = "-VALIDATION_results.json"
        print("Running validation")
    else:
        res_name = "-EXPERIMENT_results.json"
        print("Running experimentation")
    log_tag = res_name if config_name is None else res_name.replace(".json", "-"+config_name+".json")
    logger = Logger.logger(dest=results_dest, tag=log_tag, exist_ok=allow_overwrite)
    # Everything a run writes stays in its own folder.
    chats_dir = os.path.join(logger.res_folder, "chats")
    evaluator = evaluate_IR.ExperimentsEvaluator(eval_dir=os.path.join(logger.res_folder, "eval"))
    snapshot = os.path.join(logger.res_folder, "prompt_snapshot")
    os.makedirs(snapshot, exist_ok=True)
    shutil.copy2(prompts_pth, os.path.join(snapshot, os.path.basename(prompts_pth)))
    shutil.copy2(tools_pth, os.path.join(snapshot, os.path.basename(tools_pth)))
    config = {
        "runner_version": RUNNER_VERSION
        , "evaluator_version": EVALUATOR_VERSION
        , "config_name": config_name
        , "started": datetime.now().isoformat()
        , "repetition": repetition
        , "split": split
        , "incidents_json": os.path.abspath(incidents_json)
        , "incidents_json_sha256": _sha256(incidents_json)
        , "provider": provider
        , "cost_source": "OpenAI token estimate" if provider == "openai" else "OpenRouter usage"
        , "model": model
        , "model_settings": {"temperature": "not sent (provider default)"
                             , "reasoning": "not sent (provider default)"
                             , "seed": "not sent"}
        # ContextManagement "members" are plain functions (Enum skips functions)
        , "context_management": getattr(context_manager, "__name__", str(context_manager))
        , "prompts": {"path": prompts_pth, "sha256": _sha256(prompts_pth)}
        , "tools": {"path": tools_pth, "sha256": _sha256(tools_pth)}
        , "reported_time_hint": time_hint
        , "limits": {
            "max_iter": {"value": max_iter, "kind": "hard runtime limit (model turns before the final-answer prompt)"}
            , "max_records_per_call": {"value": db_fetcher.MAX_LIMIT, "kind": "hard runtime cap (None = model-requested limit only)"}
            , "tool_schema_limit_maximum": {"kind": "soft: JSON-schema hint to the model, not enforced"}
            , "prompt_tool_call_counts": {"kind": "soft: prompt instruction, not enforced"}
        }
        , "retrieval": {"similarity": "pg_trgm word_similarity", "threshold": db_fetcher.WORD_SIMILARITY_THRESHOLD
                        , "similarity_pattern_syntax": "'|' and ',' = OR of alternatives (ranked by number matched, then summed score, then best score); spaces = one phrase"
                        , "max_alternatives": db_fetcher.MAX_ALTERNATIVES
                        , "db_import": "per-incident swap_into_db() from chunk folders (db_loader)"
                        , "db_loader_sha256": _sha256(db_loader.__file__)
                        , "db_fetcher_sha256": _sha256(db_fetcher.__file__)}
        , "seed": "not supported by the runner/connector"
        , "code": git_state()
        , "cli_settings": settings
        , "samples": []
    }
    config["incident_limit"] = incident_limit
    config["execution"] = {"db_mode": db_mode, "workers": workers
                           , "max_requests_per_minute": round(60.0 / DESAI.gpt_connector.PACER.min_interval, 1)
                           if DESAI.gpt_connector.PACER.min_interval else None}
    selected = []
    for i, incident in enumerate(IssueLoader.load_incidents(incidents_json=incidents_json
                                                            , OUT=dest)):
        if not select_split(i, split):
            continue
        if incident_limit is not None and len(selected) >= incident_limit:
            break
        selected.append((i, incident))
    for i, incident in selected:
        config["samples"].append({"index": i, "incident_ts": incident.ts, "status": "pending"})
    _write_config(logger.res_folder, config)
    samples = {s["index"]: s for s in config["samples"]}

    def process(i, incident):
        # Worker: computes only; every file/config write happens in the main thread.
        if db_mode == "swap":
            incident.swap_into_db()# (yyyy-mm-ddThh:mm:ss+hh:ss)
            schema = None
        else:
            schema = db_loader.ensure_incident_schema(incident.chunk_folder)
        print()
        TIME_ANCHOR = reported_time_hint(incident.ts, enabled=time_hint)
        user_problem = TIME_ANCHOR+incident.description
        rca, retrieved, usages, _convers = DESAI.api(user_problem=user_problem
                           , context_manager=context_manager
                           , model=model
                           , provider=provider
                           , tools=tools_pth
                           , system_prompt_pth=prompts_pth
                           , max_iter=max_iter
                           , chats_dir=chats_dir
                           , chat_id="incident_%02d" % i
                           , db_schema=schema)
        return {"rca": rca["content"] or "", "retrieved": retrieved, "usages": usages
                , "conversation": _convers, "time_hint_included": bool(TIME_ANCHOR), "db_schema": schema}

    def finish(i, incident, result, error):
        # Main thread, in incident order: same records as the sequential runner.
        sample = samples[i]
        if error is not None:
            # One broken incident must not end the run (crashes lost whole runs).
            sample.update({"status": "error", "error": f"{type(error).__name__}: {str(error)[:500]}"
                           , "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__))[-3000:]})
            print("\nINCIDENT ERROR", i, sample["error"])
            config["total_cost_usd"] = round(sum(s.get("cost_usd") or 0 for s in config["samples"]), 6)
            _write_config(logger.res_folder, config)
            return
        usages = result["usages"]
        run_info = usages[2]
        sample["time_hint_included"] = result["time_hint_included"]
        sample["db_schema"] = result["db_schema"]
        sample.update(usage_summary(usages[1]))
        sample.update({"chat_log": "chats/incident_%02d" % i
                       , "status": "failed" if run_info.get("failed") else "completed"
                       , "iterations": usages[0]
                       , "api_errors": len(run_info.get("api_errors", []))
                       , "summary_tool_call_violations": run_info.get("summary_tool_call_violations", 0)
                       , "retrieved_records": len(result["retrieved"])})
        try:
            logger.log(incident=incident, rca=result["rca"], retrieved=result["retrieved"]
                       , conversation=result["conversation"], usages=usages)
        except Exception as err:
            sample.update({"status": "error", "error": f"logger: {type(err).__name__}: {str(err)[:500]}"})
        config["total_cost_usd"] = round(sum(s.get("cost_usd") or 0 for s in config["samples"]), 6)
        _write_config(logger.res_folder, config)
        if sample["status"] == "error":
            return
        try:
            evaluator.evaluate(incident, result["rca"], result["retrieved"], usages[0])
        except Exception as err:
            # Runner-side metrics only; LOGGER.json (used by the thesis analysis) is written.
            sample["evaluator_error"] = f"{type(err).__name__}: {str(err)[:500]}"
            _write_config(logger.res_folder, config)

    fatal = None
    done = {}
    next_pos = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(process, i, incident): pos for pos, (i, incident) in enumerate(selected)}
        for future in as_completed(futures):
            pos = futures[future]
            err = future.exception()
            if isinstance(err, DESAI.gpt_connector.FatalAPIError):
                fatal = err
                for f in futures:
                    f.cancel()
            done[pos] = (None, err) if err is not None else (future.result(), None)
            while next_pos in done:
                i, incident = selected[next_pos]
                result, error = done.pop(next_pos)
                finish(i, incident, result, error)
                next_pos += 1
            if fatal is not None:
                break
    if fatal is not None:
        config["aborted"] = f"{type(fatal).__name__}: {str(fatal)[:500]}"
        config["finished"] = datetime.now().isoformat()
        config["complete"] = False
        _write_config(logger.res_folder, config)
        raise fatal
    try:
        evaluator.log_results(logger.res_folder, res_name)
    except Exception as err:
        config["evaluator_error"] = f"{type(err).__name__}: {str(err)[:500]}"
    config["finished"] = datetime.now().isoformat()
    config["complete"] = (len(config["samples"]) > 0
                          and all(s["status"] == "completed" for s in config["samples"]))
    _write_config(logger.res_folder, config)
    return logger.res_folder


def usage_summary(usages_json):
    """Sum tokens and available costs over one incident's API calls."""
    try:
        usages = [u for u in json.loads(usages_json) if isinstance(u, dict)]
    except (TypeError, ValueError):
        usages = []
    costs = [u["cost"] for u in usages if isinstance(u.get("cost"), (int, float))]
    tokens = lambda key: sum(int(u.get(key) or 0) for u in usages)
    return {"api_calls": len(usages)
            , "cost_usd": round(sum(costs), 6) if costs else None
            , "prompt_tokens": tokens("prompt_tokens")
            , "completion_tokens": tokens("completion_tokens")
            , "reasoning_tokens": sum(int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
                                    for u in usages)}


DEFAULT_MODEL = "openai/gpt-6-luna"


def add_provider_arguments(parser):
    parser.add_argument("--provider", choices=tuple(DESAI.gpt_connector.PROVIDER_KEYS),
                        default="openrouter", help="API provider (default: %(default)s)")
    parser.add_argument("-m", "--model", help="Provider model ID. Defaults to "
                        f"{DEFAULT_MODEL} on OpenRouter or {DESAI.gpt_connector.OPENAI_DEFAULT_MODEL} on OpenAI.")


def resolve_model(model, provider):
    if provider == "openai":
        return (model or DESAI.gpt_connector.OPENAI_DEFAULT_MODEL).removeprefix("openai/")
    return model or DEFAULT_MODEL

# Prompt configurations of the thesis appendix ("Prompt Optimization"); see
# prompt_engineering/variants/README.md for provenance.
PRESETS = {
    "before-po": {"prompts": "variants/before-po/DESAI-prompts.json"
                  , "tools": "variants/before-po/DESAI-tools.json", "time_hint": False}
    , "after-po": {"prompts": "variants/after-po/DESAI-prompts.json"
                   , "tools": "variants/after-po/DESAI-tools.json", "time_hint": True}
    , "extended": {"prompts": "DESAI-prompts.json", "tools": "DESAI-tools.json", "time_hint": True}
}

DEFAULT_PRESET = "extended"

EXAMPLES = """
examples:
  # default configuration (preset "extended", model %s), validation split
  python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -s -v

  # the thesis's three prompt configurations with the thesis's model
  python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -s -v \\
      -m openai/gpt-4o-mini --preset before-po --config-name before-po

  # preset with one part overridden, 2 repetitions, own output folder
  python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -s \\
      --split validation --preset after-po --no-reported-time-hint \\
      --config-name after-po_nohint --repetitions 2 --out ./out/runs_v2/

  # own prompt file
  python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -s -v \\
      --prompts ./my_prompts/prompts.json --config-name my-prompts

Each run gets its own folder (under --out, default out/chunked_<size>/) with
LOGGER.json, *_results.json, run_config.json, prompt_snapshot/, chats/ and eval/.
""" % DEFAULT_MODEL


def build_parser():
    parser = argparse.ArgumentParser(
       description="Experiment setup"
       , epilog=EXAMPLES
       , formatter_class=argparse.RawDescriptionHelpFormatter
       )
    parser.add_argument(
        "-t", "--trunk",
        dest="trunk",
        action="store_true",
        help="Truncation context management strategy"
    )
    parser.add_argument(
         "-s", "--summarization",
         dest="summarization",
         action="store_true",
         help="Summarization context management strategy"
     )
    parser.add_argument(
         "-i", "--incidents",
         dest="incidents",
         default="chunked_incidents.json"
         ,help="The chunked_incidents.json file"
     )
    add_provider_arguments(parser)
    parser.add_argument(
          "-a", "--target_analysis",
          dest="target_analysis",
          action="store_true",
          help="Target analysis instead of experiments"
      )
    parser.add_argument(
          "-v", "--validation",
          dest="validation",
          action="store_true",
          help="Validation set experimentation (same as --split validation)"
      )
    parser.add_argument(
          "--split",
          choices=("validation", "heldout"),
          default=None,
          help="Incident split: validation = every 5th incident (i %% 5 == 0), heldout = the rest (default: heldout unless -v)"
      )
    parser.add_argument(
          "--preset",
          choices=tuple(PRESETS),
          default=DEFAULT_PRESET,
          help="Prompt configuration of the thesis appendix: before-po (hint off), after-po, extended (default: %(default)s); --prompts/--tools/--(no-)reported-time-hint override single parts"
      )
    parser.add_argument(
          "--prompts",
          default=None,
          help="Prompt JSON (initial_prompt, summarization, force_end_prompt); bare/relative names also resolve in the package prompt_engineering/ folder (default: from --preset)"
      )
    parser.add_argument(
          "--tools",
          default=None,
          help="Tool schema JSON; resolved like --prompts (default: from --preset)"
      )
    parser.add_argument(
          "--reported-time-hint",
          dest="time_hint",
          action=argparse.BooleanOptionalAction,
          default=None,
          help="Prepend the reported incident date to the incident description (default: from --preset)"
      )
    parser.add_argument(
          "--max-iter",
          type=int,
          default=DESAI.DEFAULT_MAX_ITER,
          help="Hard limit on model turns before the final-answer prompt (default: %(default)s)"
      )
    parser.add_argument(
          "--max-records",
          type=int,
          default=None,
          help="Hard cap on records returned per tool call (default: none, the model's requested limit is used)"
      )
    parser.add_argument(
          "--similarity-threshold",
          type=float,
          default=db_fetcher.WORD_SIMILARITY_THRESHOLD,
          help="pg_trgm word_similarity threshold for similarity_pattern (default: %(default)s, an unvalidated candidate)"
      )
    parser.add_argument(
          "--repetitions",
          type=int,
          default=1,
          help="Number of repeated runs over the split (default: %(default)s)"
      )
    parser.add_argument(
          "--config-name",
          default=None,
          help="Label added to the result folder name and recorded in run_config.json"
      )
    parser.add_argument(
          "--out",
          default=None,
          help="Result folder root (default: out/chunked_<size>/)"
      )
    parser.add_argument(
          "--workers",
          type=int,
          default=1,
          help="Incidents processed at the same time (cached DB mode only; default %(default)s)"
      )
    parser.add_argument(
          "--max-rpm",
          type=float,
          default=60.0,
          help="Polite limit: API requests per minute over all workers (default %(default)s)"
      )
    parser.add_argument(
          "--db-mode",
          choices=("cached", "swap"),
          default="cached",
          help="cached: every incident loaded once into its own schema and reused (default); "
               "swap: the historical shared log_chunks table, reloaded per incident (one worker)"
      )
    parser.add_argument(
          "--incident-limit",
          type=int,
          default=None,
          help="Only the first N incidents of the split (smoke tests; recorded in run_config.json)"
      )
    parser.add_argument(
          "--allow-overwrite",
          action="store_true",
          help="Allow writing into an already existing result folder"
      )
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.model = resolve_model(args.model, args.provider)
    if args.summarization:
        context_manager = message_manager.ContextManagement.SUMMARIZATION
    elif args.trunk:
        context_manager = message_manager.ContextManagement.TRUNCATION
    else:
        context_manager = message_manager.ContextManagement.NONE
    if args.split is None:
        args.split = "validation" if args.validation else "heldout"
    elif args.validation and args.split != "validation":
        parser.error("-v/--validation conflicts with --split "+args.split)
    if args.max_iter < 1 or args.repetitions < 1:
        parser.error("--max-iter and --repetitions must be >= 1")
    if args.max_records is not None and args.max_records < 1:
        parser.error("--max-records must be >= 1")
    if args.incident_limit is not None and args.incident_limit < 1:
        parser.error("--incident-limit must be >= 1")
    if args.workers < 1 or args.max_rpm <= 0:
        parser.error("--workers must be >= 1 and --max-rpm > 0")
    if args.db_mode == "swap" and args.workers != 1:
        parser.error("--db-mode swap shares one table: only --workers 1")
    if not 0.0 < args.similarity_threshold <= 1.0:
        parser.error("--similarity-threshold must be in (0, 1]")
    preset = PRESETS[args.preset]
    if args.prompts is None:
        args.prompts = preset["prompts"]
    if args.tools is None:
        args.tools = preset["tools"]
    if args.time_hint is None:
        args.time_hint = preset["time_hint"]
    args.prompts = DESAI.resolve_prompt_path(args.prompts)
    args.tools = DESAI.resolve_prompt_path(args.tools)
    if not args.target_analysis:
        try:
            validate_prompts(args.prompts)
            validate_tools(args.tools)
        except ConfigError as err:
            parser.error(str(err))
    return context_manager, args


if __name__ == "__main__":
    context_manager, args = parse_args()
    incidents_json, target_analysis = args.incidents, args.target_analysis
    chunk_size = incidents_json.replace("\\","/").split("/")[-2]
    if not target_analysis:
        db_fetcher.WORD_SIMILARITY_THRESHOLD = args.similarity_threshold
        db_fetcher.MAX_LIMIT = args.max_records
        settings = {k: v for k, v in vars(args).items()}
        DESAI.gpt_connector.PACER.configure(min_interval=60.0 / args.max_rpm, max_in_flight=args.workers)
        try:
            DESAI.gpt_connector.require_api_key(args.provider)
            # Only the shared table needs exclusive use; schemas are per incident.
            with (db_lock() if args.db_mode == "swap" else contextlib.nullcontext()):
                for rep in range(1, args.repetitions+1):
                    print(f"===== RUN {rep} / {args.repetitions} =====")
                    folder = api(context_manager=context_manager, incidents_json=incidents_json, chunk_size=chunk_size
                        , model=args.model, provider=args.provider, VALIDATION=(args.split == "validation")
                        , prompts_pth=args.prompts, tools_pth=args.tools, time_hint=args.time_hint
                        , max_iter=args.max_iter, config_name=args.config_name, out_dir=args.out
                        , repetition=rep, allow_overwrite=args.allow_overwrite, settings=settings
                        , incident_limit=args.incident_limit, db_mode=args.db_mode, workers=args.workers)
                    print("\nRESULT_FOLDER:", os.path.abspath(folder))
        except ExperimentLocked as err:
            print("ERROR:", err, file=sys.stderr)
            sys.exit(EXIT_LOCKED)
        except DESAI.gpt_connector.FatalAPIError as err:
            # no credits / bad key: stop instead of failing every remaining incident
            print("FATAL API ERROR:", err, file=sys.stderr)
            sys.exit(EXIT_FATAL_API)
    else:
        if not chunk_size.isdigit():
            chunk_size = None
        coverage_analysis_api(incidents_json, chunking=chunk_size)
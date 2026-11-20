"""Unattended thesis experiment campaign: all prompt configurations x N repetitions.

    python -m rca.ai_agent.experiments.campaign --name thesis-final --repetitions 10 --budget-usd 20

Run from the project root (the folder containing out/). Each run is a separate
DESExperiments process; a run is *complete* when every incident finished. The
command is resumable: run it again (same --name) and only missing runs are
started. Crashed/interrupted runs stay on disk and are ignored; a repetition is
retried up to --max-attempts times. At the end (or with --summarize-only) the
summary and the thesis tables/figures are written to <campaign>/summary/.
See EXPERIMENT_CAMPAIGN.md.
"""
import argparse
import contextlib
import io
import json
import math
import os
import warnings
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

from rca.ai_agent.experiments import DESExperiments as dx

# preset -> label used in the thesis
CONFIGS = {"before-po": "Before PO"
           , "after-po": "Optimized"
           , "extended": "Optimized + extended retrieval"}

COMPONENTS = ("Retrieval", "Summarization", "Final output")

TARGETS = (("reference", "line_count"), ("line2_exact", "line_count")
           , ("reference", "line_lengths"), ("line2_exact", "line_lengths"))

EXIT_LOCKED = dx.EXIT_LOCKED

EXIT_FATAL_API = dx.EXIT_FATAL_API

SETTINGS_KEYS = ("model", "split", "incidents", "incidents_sha256", "incident_limit", "configs")


# ---------------------------------------------------------------- run state

def expected_incidents(incidents_json, split, incident_limit=None):
    with open(incidents_json, encoding="utf-8") as fp:
        n = len(json.load(fp))
    count = sum(1 for i in range(n) if dx.select_split(i, split))
    return count if incident_limit is None else min(count, incident_limit)


def run_status(folder, expected):
    """'complete' | 'incomplete' | 'broken' and details for one run folder."""
    folder = Path(folder)
    try:
        cfg = json.loads((folder / dx.RUN_CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "broken", {}
    samples = cfg.get("samples", [])
    try:
        logged = len(json.loads((folder / "LOGGER.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        logged = 0
    info = {"started": cfg.get("started"), "finished": cfg.get("finished")
            , "samples": len(samples), "logged": logged
            , "completed": sum(s.get("status") == "completed" for s in samples)
            , "cost_usd": cfg.get("total_cost_usd") or 0.0
            , "repetition_label": cfg.get("config_name")}
    ok = (cfg.get("finished") is not None and len(samples) == expected
          and info["completed"] == expected and logged == expected)
    return ("complete" if ok else "incomplete"), info


def config_runs(campaign_dir, config, expected):
    """All run folders of one configuration, oldest first, with status."""
    d = Path(campaign_dir) / config
    if not d.is_dir():
        return []
    runs = []
    for f in sorted(p for p in d.iterdir() if p.is_dir()):
        status, info = run_status(f, expected)
        runs.append({"folder": str(f), "status": status, **info})
    return runs


def campaign_cost(campaign_dir, configs, expected):
    return round(sum(r.get("cost_usd") or 0 for c in configs
                     for r in config_runs(campaign_dir, c, expected)), 6)


def next_job(campaign_dir, configs, repetitions, expected, attempts, max_attempts):
    """Repetition-major order: (config, repetition) of the next run to start,
    or None. attempts: {"config:rep": n}."""
    for rep in range(1, repetitions + 1):
        for config in configs:
            done = sum(r["status"] == "complete" for r in config_runs(campaign_dir, config, expected))
            if done >= rep:
                continue
            if attempts.get(f"{config}:{rep}", 0) >= max_attempts:
                continue
            return config, rep
    return None


# ---------------------------------------------------------------- campaign

def load_or_create_campaign(campaign_dir, settings, force=False):
    path = Path(campaign_dir) / "campaign.json"
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state["settings"].get("provider", "openrouter") != settings.get("provider", "openrouter"):
            raise SystemExit(f"campaign provider differs from {path}; use another --name")
        changed = {k: (state["settings"].get(k), settings.get(k)) for k in SETTINGS_KEYS
                   if state["settings"].get(k) != settings.get(k)}
        if changed and not force:
            raise SystemExit(f"campaign settings differ from {path}: {changed}\n"
                             "use another --name, or --force to continue anyway")
        state["settings"].update({k: v for k, v in settings.items() if k not in SETTINGS_KEYS})
    else:
        os.makedirs(campaign_dir, exist_ok=True)
        state = {"created": datetime.now().isoformat(), "settings": settings, "attempts": {}, "events": []}
    save_campaign(campaign_dir, state)
    return state


def save_campaign(campaign_dir, state):
    path = Path(campaign_dir) / "campaign.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def run_one(args, campaign_dir, config, rep, attempt):
    out = Path(campaign_dir) / config
    logs = Path(campaign_dir) / "logs"
    out.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-u", "-m", "rca.ai_agent.experiments.DESExperiments"
           , "-i", args.incidents, "-s", "--split", args.split, "--preset", config
           , "--provider", args.provider, "-m", args.model, "--config-name", f"{config}-r{rep:02d}-a{attempt}"
           , "--out", str(out), "--workers", str(args.workers), "--max-rpm", str(args.max_rpm)]
    if args.incident_limit is not None:
        cmd += ["--incident-limit", str(args.incident_limit)]
    log_path = logs / f"{config}-r{rep:02d}-a{attempt}.log"
    env = dict(os.environ, MPLBACKEND="Agg")
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(" ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=args.root)
    folder = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("RESULT_FOLDER:"):
            folder = line.split(":", 1)[1].strip()
    return proc.returncode, folder, str(log_path)


def run_campaign(args, campaign_dir, expected):
    args.model = dx.resolve_model(args.model, args.provider)
    settings = {"model": args.model, "provider": args.provider, "split": args.split, "incidents": os.path.abspath(args.incidents)
                , "incidents_sha256": dx._sha256(args.incidents), "incident_limit": args.incident_limit
                , "configs": args.configs, "repetitions": args.repetitions
                , "max_attempts": args.max_attempts, "budget_usd": args.budget_usd}
    state = load_or_create_campaign(campaign_dir, settings, force=args.force)
    while True:
        job = next_job(campaign_dir, args.configs, args.repetitions, expected
                       , state["attempts"], args.max_attempts)
        if job is None:
            break
        spent = campaign_cost(campaign_dir, args.configs, expected)
        if args.budget_usd is not None and spent >= args.budget_usd:
            print(f"BUDGET reached: ${spent:.4f} >= ${args.budget_usd}; no new runs started")
            state["events"].append({"time": datetime.now().isoformat(), "event": "budget_reached", "spent": spent})
            save_campaign(campaign_dir, state)
            break
        config, rep = job
        key = f"{config}:{rep}"
        attempt = state["attempts"].get(key, 0) + 1
        state["attempts"][key] = attempt
        save_campaign(campaign_dir, state)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {config} repetition {rep}/{args.repetitions}"
              f" attempt {attempt}/{args.max_attempts} (spent so far ${spent:.4f})", flush=True)
        t0 = time.time()
        code, folder, log_path = run_one(args, campaign_dir, config, rep, attempt)
        status, info = run_status(folder, expected) if folder else ("broken", {})
        event = {"time": datetime.now().isoformat(), "config": config, "repetition": rep, "attempt": attempt
                 , "exit_code": code, "folder": folder, "status": status, "minutes": round((time.time()-t0)/60, 1)
                 , "log": log_path, **{k: info.get(k) for k in ("completed", "samples", "cost_usd")}}
        state["events"].append(event)
        save_campaign(campaign_dir, state)
        print(f"    -> {status} (exit {code}, {event['minutes']} min, {info.get('completed')}/{expected} incidents,"
              f" ${info.get('cost_usd') or 0:.4f})", flush=True)
        if code == EXIT_LOCKED:
            raise SystemExit("another experiment is using the database; campaign stopped (re-run later to resume)")
        if code == EXIT_FATAL_API:
            raise SystemExit(f"{args.provider} requests stopped (see {log_path}); re-run to resume")
    return state


# ---------------------------------------------------------------- summary

def corrected_sub_evaluate_txt(inputs, respect_ix):
    """Corrected substring evaluator (audit/audit_thesis_recall_complete.py):
    one boolean per source, whether ANY source line contains the target line."""
    from rca.results import Logger as log
    prepared = [log.prep(text) for text in inputs]
    return [[True if j == respect_ix else any(target in source_line for source_line in source)
             for j, source in enumerate(prepared)]
            for target in prepared[respect_ix]]


def score_run(logger_path, corrected):
    """{(target, aspect, component): {incident id: recall}} for one run."""
    from rca.results import Logger as log
    from rca.results import xBinTable as xb
    raw = json.loads(Path(logger_path).read_text(encoding="utf-8"))
    ids = [str(s["incident id"]) for s in raw]
    old = xb.sub_evaluate_txt
    if corrected:
        xb.sub_evaluate_txt = corrected_sub_evaluate_txt
    try:
        trans = log.transform(str(logger_path))
        scores = xb.grounded_information_SOLO_sample_wise(xb.evaluate_samples(trans, SUB=True), trans
                                                          , ONLY_GROUNDED=True)
    finally:
        xb.sub_evaluate_txt = old
    return {(t, a, c): dict(zip(ids, scores[t][a][ci]))
            for t, a in TARGETS for ci, c in enumerate(COMPONENTS)}


def chat_stats(run_folder):
    """record_selector calls / empty results from the run's chats/."""
    calls = empty = 0
    for d in sorted((Path(run_folder) / "chats").glob("incident_*")):
        if not d.is_dir():
            continue
        tool_calls, results = {}, {}
        for f in sorted(d.glob("turn*.json")):
            for m in json.loads(f.read_text(encoding="utf-8")):
                if not isinstance(m, dict):
                    continue
                for tc in m.get("tool_calls") or []:
                    if tc.get("function", {}).get("name") == "record_selector":
                        tool_calls[tc["id"]] = True
                if m.get("role") == "tool":
                    results[m.get("tool_call_id")] = str(m.get("content"))
        for cid in tool_calls:
            calls += 1
            r = results.get(cid, "").strip()
            try:
                empty += len(json.loads(r)) == 0
            except ValueError:
                empty += r in ("", "None")
    return calls, empty


def summarize(campaign_dir, configs, repetitions, expected, thesis_outputs=True):
    from scipy.stats import wilcoxon
    out = Path(campaign_dir) / "summary"
    out.mkdir(parents=True, exist_ok=True)
    report = {"generated": datetime.now().isoformat(), "configs": {}, "recall": {}, "wilcoxon": {}}
    used = {}
    for config in configs:
        runs = config_runs(campaign_dir, config, expected)
        complete = [r for r in runs if r["status"] == "complete"][:repetitions]
        used[config] = complete
        calls = empty = 0
        for r in complete:
            c, e = chat_stats(r["folder"])
            calls, empty = calls + c, empty + e
        cfgs = [json.loads((Path(r["folder"]) / dx.RUN_CONFIG).read_text(encoding="utf-8")) for r in runs
                if r["status"] != "broken"]
        samples = [s for c in cfgs for s in c.get("samples", [])]
        report["configs"][config] = {
            "label": CONFIGS[config], "complete_runs_used": len(complete), "runs_on_disk": len(runs)
            , "incomplete_runs": sum(r["status"] != "complete" for r in runs)
            , "cost_usd_all_runs": round(sum(r.get("cost_usd") or 0 for r in runs), 4)
            , "incident_status_all_runs": {k: sum(s.get("status") == k for s in samples)
                                           for k in ("completed", "failed", "error", "started")}
            , "api_errors_all_runs": sum(s.get("api_errors") or 0 for s in samples)
            , "record_selector_calls": calls, "empty_results": empty
            , "empty_rate": round(empty / calls, 4) if calls else None
            , "incidents_without_records": sum(1 for c in cfgs for s in c.get("samples", [])
                                               if s.get("status") == "completed" and not s.get("retrieved_records"))
            , "folders": [r["folder"] for r in complete]}
    for corrected in (False, True):
        ev = "corrected" if corrected else "original"
        scores = {c: [score_run(Path(r["folder"]) / "LOGGER.json", corrected) for r in used[c]] for c in configs}
        report["recall"][ev] = {}
        report["wilcoxon"][ev] = {}
        for t, a in TARGETS:
            for comp in COMPONENTS:
                key = (t, a, comp)
                name = f"{t}/{a}/{comp}"
                per_id = {}
                row = {}
                for c in configs:
                    vals = [v for run in scores[c] for v in run[key].values()]
                    by_id = defaultdict(list)
                    for run in scores[c]:
                        for ident, v in run[key].items():
                            by_id[ident].append(v)
                    per_id[c] = {i: mean(v) for i, v in by_id.items()}
                    row[c] = {"pooled_mean": round(mean(vals), 4) if vals else None
                              , "incident_mean": round(mean(per_id[c].values()), 4) if per_id[c] else None
                              , "n_observations": len(vals), "n_incidents": len(per_id[c])}
                report["recall"][ev][name] = row
                tests = {}
                for i, a_cfg in enumerate(configs):
                    for b_cfg in configs[i+1:]:
                        common = sorted(set(per_id[a_cfg]) & set(per_id[b_cfg]))
                        xa = [per_id[a_cfg][k] for k in common]
                        xb_ = [per_id[b_cfg][k] for k in common]
                        diffs = [y - x for x, y in zip(xa, xb_)]
                        res = {"n": len(common), "mean_difference": round(mean(diffs), 4) if diffs else None
                               , "better": sum(d > 0 for d in diffs), "worse": sum(d < 0 for d in diffs)
                               , "equal": sum(d == 0 for d in diffs), "p_value": None}
                        if any(diffs):
                            try:
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore", RuntimeWarning)  # tiny n
                                    p = float(wilcoxon(xa, xb_).pvalue)
                                res["p_value"] = None if math.isnan(p) else round(p, 4)
                            except ValueError:
                                pass
                        tests[f"{a_cfg} -> {b_cfg}"] = res
                report["wilcoxon"][ev][name] = tests
    (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "summary.md").write_text(render_markdown(report, configs), encoding="utf-8")
    if thesis_outputs and all(used[c] for c in configs):
        from rca.results import results_statistics as rs
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rs.generate({CONFIGS[c]: [str(Path(r["folder"]) / "LOGGER.json") for r in used[c]] for c in configs}
                            , outdir=str(out / "thesis"), rouge_key=CONFIGS[configs[-1]])
        except Exception as err:
            report["thesis_outputs_error"] = f"{type(err).__name__}: {err}"
            (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (out / "thesis").mkdir(exist_ok=True)
        (out / "thesis" / "latex_tables_and_tests.txt").write_text(buf.getvalue(), encoding="utf-8")
    return report


def render_markdown(report, configs):
    lines = [f"# Campaign summary ({report['generated']})", "", "## Runs", ""
             , "| Config | Complete runs used | Incomplete runs | Incidents completed/failed/error | API errors"
               " | Empty search results | Incidents without records | Cost (all runs) |"
             , "|---|---|---|---|---|---|---|---|"]
    for c in configs:
        r = report["configs"][c]
        st = r["incident_status_all_runs"]
        rate = f"{r['empty_results']}/{r['record_selector_calls']}" + (f" ({r['empty_rate']:.0%})" if r["empty_rate"] is not None else "")
        lines.append(f"| {r['label']} | {r['complete_runs_used']} | {r['incomplete_runs']} | {st['completed']}/{st['failed']}/{st['error']}"
                     f" | {r['api_errors_all_runs']} | {rate} | {r['incidents_without_records']} | ${r['cost_usd_all_runs']:.4f} |")
    for ev in ("original", "corrected"):
        lines += ["", f"## Chained recall, {ev} substring evaluator (incident means; pooled in brackets)", ""
                  , "| Target / aspect / component | " + " | ".join(report["configs"][c]["label"] for c in configs) + " |"
                  , "|---|" + "---|" * len(configs)]
        for name, row in report["recall"][ev].items():
            cells = []
            for c in configs:
                v = row[c]
                cells.append("–" if v["incident_mean"] is None else f"{v['incident_mean']:.3f} ({v['pooled_mean']:.3f})")
            lines.append(f"| {name.replace('line2_exact', 'grounded')} | " + " | ".join(cells) + " |")
        lines += ["", f"### Paired Wilcoxon tests on per-incident means ({ev} evaluator)", ""
                  , "| Target / aspect / component | Comparison | n | Mean diff | Better/worse/equal | p |"
                  , "|---|---|---|---|---|---|"]
        for name, tests in report["wilcoxon"][ev].items():
            for comp, t in tests.items():
                p = "–" if t["p_value"] is None else f"{t['p_value']:.4f}"
                md = "–" if t["mean_difference"] is None else f"{t['mean_difference']:+.3f}"
                lines.append(f"| {name.replace('line2_exact', 'grounded')} | {comp} | {t['n']} | {md}"
                             f" | {t['better']}/{t['worse']}/{t['equal']} | {p} |")
    lines += ["", "Thesis tables/figures (original evaluator, as in the thesis): `summary/thesis/`."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True, help="Campaign name; folder out/campaigns/<name>/ (resumes if it exists)")
    p.add_argument("--root", default=".", help="Project root containing out/ (default: current folder)")
    p.add_argument("-i", "--incidents", default="out/3000/chunked_incidents.json")
    dx.add_provider_arguments(p)
    p.add_argument("--split", choices=("heldout", "validation"), default="heldout")
    p.add_argument("--configs", nargs="+", choices=tuple(CONFIGS), default=list(CONFIGS)
                   , help="Prompt configurations, in this order (default: all three)")
    p.add_argument("--repetitions", type=int, default=10)
    p.add_argument("--max-attempts", type=int, default=3, help="Attempts per configuration and repetition")
    p.add_argument("--budget-usd", type=float, default=None, help="No new run starts once the recorded cost reaches this")
    p.add_argument("--workers", type=int, default=4
                   , help="Incidents processed at the same time inside each run (default %(default)s)")
    p.add_argument("--max-rpm", type=float, default=60.0
                   , help="Polite limit: API requests per minute over all workers (default %(default)s)")
    p.add_argument("--no-preload", action="store_true", help="Do not load all incident schemas before the first run")
    p.add_argument("--incident-limit", type=int, default=None, help="Smoke tests: first N incidents of the split")
    p.add_argument("--summarize-only", action="store_true")
    p.add_argument("--no-thesis-outputs", action="store_true", help="Skip LaTeX tables/figures/ROUGE")
    p.add_argument("--force", action="store_true", help="Continue a campaign although its settings differ")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.model = dx.resolve_model(args.model, args.provider)
    args.root = os.path.abspath(args.root)
    os.chdir(args.root)
    if args.repetitions < 1 or args.max_attempts < 1 or args.workers < 1 or args.max_rpm <= 0:
        raise SystemExit("--repetitions, --max-attempts and --workers must be >= 1, --max-rpm > 0")
    campaign_dir = os.path.join(args.root, "out", "campaigns", args.name)
    expected = expected_incidents(args.incidents, args.split, args.incident_limit)
    print(f"campaign {campaign_dir}: {len(args.configs)} configs x {args.repetitions} repetitions"
          f" x {expected} incidents, {args.provider} model {args.model}")
    if not args.summarize_only:
        connector = dx.DESAI.gpt_connector
        if (args.provider == "openai" and args.budget_usd is not None
                and args.model not in connector.OPENAI_TEXT_RATES):
            raise SystemExit(f"Budget tracking has no OpenAI token rates for {args.model}.")
        try:
            connector.require_api_key(args.provider)
        except connector.FatalAPIError as err:
            raise SystemExit(str(err)) from err
        # (smoke tests with --incident-limit load their few incidents on demand)
        if not args.no_preload and args.incident_limit is None:
            # every incident of the split once into its schema (reused by all runs)
            from rca.ai_agent.knowledge_base import db_loader
            print("preloading incident schemas ...", flush=True)
            db_loader.preload(args.incidents, split=args.split, workers=4)
        run_campaign(args, campaign_dir, expected)
    report = summarize(campaign_dir, args.configs, args.repetitions, expected
                       , thesis_outputs=not args.no_thesis_outputs)
    for c in args.configs:
        r = report["configs"][c]
        print(f"  {r['label']}: {r['complete_runs_used']}/{args.repetitions} complete runs, ${r['cost_usd_all_runs']:.4f}")
    print("summary:", os.path.join(campaign_dir, "summary", "summary.md"))


if __name__ == "__main__":
    main()

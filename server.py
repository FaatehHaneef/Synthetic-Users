"""Local server for the Synthetic Users interface. Run with: python server.py"""
import csv
import os
import pathlib
import threading
import uuid
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

from synthusers.analyze import (ALIASES_PATH, CHARTS, IGNORE, PAPER_BASELINES, PAPER_WORDS, REVIEW_FIELDS, analyze_records, chart_rows,
                                clean_title, compute_metrics, ensure_review_sample, load_aliases, results_dir, review_tally,
                                save_aliases, strip_lead_in, write_outputs)
from synthusers.generate import (DEFAULT_MODEL, QUOTA_LOG_PATH, RUNS_DIR, ApiError, GeminiProvider, parse_reply, quality_status, read_records)
from synthusers.keys import AllKeysExhausted, load_keys
from synthusers.prompts import PERSONAS, PROMPT_1, SYSTEM_INSTRUCTION, build_prompt
from synthusers.themes import tag_answer, theme_counts

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "web" / "dist"
RUN_NAME = "gemini-main"
LIVE_SIZES = (1, 5, 10)
RETRY_BUDGET_SECONDS = 25
GROUP_NAMES = {"default": "Plain prompt", "persona": "With persona"}
MESSAGES = {
    "quota": "API key quota exhausted.",
    "busy": "Google's servers didn't respond.",
    "offline": "No internet connection.",
    "refused": "These API keys were refused by Google.",
    "other": "The request didn't go through. Try again.",
    "no_run": "No saved run found.",
}


def default_provider():
    return GeminiProvider(load_keys(), DEFAULT_MODEL, rpm=5, log_path=QUOTA_LOG_PATH, retry_budget=RETRY_BUDGET_SECONDS)


def failure(kind):
    return {"kind": kind, "message": MESSAGES[kind]}


def out_of_keys_kind(provider):
    """Quota, unless Google refused every key."""
    if provider is not None and len(provider.pool.invalid) == len(provider.pool.keys):
        return "refused"
    return "quota" if provider is not None else "refused"


def live_item(answer, title, words):
    return {"game": strip_lead_in(title).strip(" ."), "answer": answer, "words": words, "tags": tag_answer(answer)}


def run_live_job(job, count, make_provider):
    provider = None
    records = []
    try:
        provider = make_provider()
        attempts = 0
        while len(job["items"]) < count and attempts < count + 3:
            attempts += 1
            result = provider.generate(build_prompt(), SYSTEM_INSTRUCTION, 1)
            candidate = result.candidates[0] if result.candidates else None
            if candidate is None:
                continue
            answer, title = parse_reply(candidate.text)
            if quality_status(answer, title) != "valid":
                continue
            words = len(answer.split())
            job["items"].append(live_item(answer, title, words))
            records.append({"title_raw": title, "words": words})
            job["done"] = len(job["items"])
        if len(job["items"]) < count:
            job["error"] = failure("other")
    except AllKeysExhausted:
        job["error"] = failure(out_of_keys_kind(provider))
    except ApiError as error:
        job["error"] = failure(error.kind if error.kind in MESSAGES else "other")
    except Exception:  # never show a raw error on screen
        job["error"] = failure("other")
    if records:
        metrics = compute_metrics(records, load_aliases())
        top = metrics["ranked"][0]
        job["summary"] = {"game": top["title"], "count": top["count"], "total": metrics["mentions"]}
    job["state"] = "done"


def run_path():
    return RUNS_DIR / f"{RUN_NAME}.jsonl"


def load_run():
    records = read_records(run_path())
    return records, analyze_records(records, load_aliases()) if records else None


def persona_rows(records, aliases):
    rows = []
    for persona_id, persona in enumerate(PERSONAS):
        subset = [r for r in records if r["status"] == "valid" and r["persona_id"] == persona_id]
        if subset:
            metrics = compute_metrics(subset, aliases)
            top = metrics["ranked"][0]
            rows.append({"persona": persona, "game": top["title"], "count": top["count"], "total": metrics["mentions"],
                         "others": [{"title": g["title"], "count": g["count"]} for g in metrics["ranked"][1:4]]})
    return rows


def read_review(directory, records):
    path = ensure_review_sample(records, directory)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def comparison(analysis):
    rows = [{"group": f"{name} (paper)", "source": "paper", "mentions": b["mentions"], "distinct": b["distinct"],
             "per100": round(b["distinct_per_100"], 1), "topGame": b["top_game"], "top1": round(b["top1_share"], 1),
             "top3": round(b["top3_share"], 1)} for name, b in PAPER_BASELINES.items()]
    for condition, g in analysis["groups"].items():
        rows.append({"group": f"{GROUP_NAMES[condition]} (our run)", "source": "ours", "mentions": g["mentions"], "distinct": g["distinct"],
                     "per100": round(g["distinct_per_100"], 1), "topGame": g["top_game"], "top1": round(g["top1_share"], 1),
                     "top3": round(g["top3_share"], 1), "low": round(g["top1_low"], 1), "high": round(g["top1_high"], 1)})
    return rows


def create_app(make_provider=default_provider):
    app = Flask(__name__, static_folder=None)
    jobs = {}

    @app.post("/api/live")
    def start_live():
        count = (request.get_json(silent=True) or {}).get("count")
        if count not in LIVE_SIZES:
            return jsonify(error=failure("other")), 400
        job_id = uuid.uuid4().hex
        jobs[job_id] = {"state": "running", "done": 0, "total": count, "items": [], "summary": None, "error": None}
        threading.Thread(target=run_live_job, args=(jobs[job_id], count, make_provider), daemon=True).start()
        return jsonify(id=job_id)

    @app.get("/api/live/<job_id>")
    def live_status(job_id):
        return jsonify(jobs[job_id]) if job_id in jobs else (jsonify(error=failure("other")), 404)

    @app.get("/api/saved")
    def saved():
        records, analysis = load_run()
        if not analysis:
            return jsonify(error=failure("no_run")), 404
        groups = {}
        for condition, g in analysis["groups"].items():
            groups[condition] = {"share": round(g["top1_share"], 1), "game": g["top_game"], "total": g["mentions"], "distinct": g["distinct"],
                                 "games": [{"title": r["title"], "count": r["count"]} for r in g["ranked"][:6]]}
        human = PAPER_BASELINES["Real people"]
        return jsonify(groups=groups, personas=persona_rows(records, load_aliases()),
                       human={"share": round(human["top1_share"], 1), "distinct": human["distinct"], "total": human["mentions"]})

    def inspect_payload():
        records, analysis = load_run()
        aliases = load_aliases()
        directory = results_dir(run_path())
        review = read_review(directory, records)
        valid = [r for r in records if r["status"] == "valid"]
        counts, names = {}, {}
        for group in analysis["groups"].values():
            for row in group["ranked"]:
                counts[row["key"]] = counts.get(row["key"], 0) + row["count"]
                names.setdefault(row["key"], row["title"])
        return {
            "model": analysis["model"], "requests": analysis["requests"], "isFake": analysis["is_fake_data"],
            "comparison": comparison(analysis),
            "charts": [{"id": m, "title": t, "unit": x, "rows": [{**r, "value": round(r["value"], 1)} for r in chart_rows(analysis, m)]}
                       for m, (t, x) in CHARTS.items()],
            "games": {c: {"name": GROUP_NAMES[c], "rows": [{"title": r["title"], "count": r["count"]} for r in g["ranked"]]}
                      for c, g in analysis["groups"].items()},
            "personas": persona_rows(records, aliases),
            "lengths": [{"group": f"{n} (paper, Exp 1)", "words": w} for n, w in PAPER_WORDS.items()]
            + [{"group": f"{GROUP_NAMES[c]} (our run)", "words": round(g["mean_words"], 1)} for c, g in analysis["groups"].items()],
            "themes": {c: {"name": GROUP_NAMES[c], "rows": [{"theme": t, "count": n}
                                                            for t, n in theme_counts(r["answer"] for r in valid if r["condition"] == c)]}
                       for c in analysis["groups"]},
            "prompt": {"interview": PROMPT_1, "system": SYSTEM_INSTRUCTION, "personas": PERSONAS},
            "review": {"rows": [{**row, "title": strip_lead_in(row["title"]).strip(" .")} for row in review], "tally": review_tally(review)},
            "titles": sorted(({"key": k, "title": names[k], "count": counts[k]} for k in counts), key=lambda r: -r["count"]),
            "aliases": [{"from": k, "to": v} for k, v in aliases.items()],
        }

    @app.get("/api/inspect")
    def inspect():
        return jsonify(inspect_payload()) if run_path().exists() else (jsonify(error=failure("no_run")), 404)

    @app.post("/api/review")
    def save_review():
        records = read_records(run_path())
        directory = results_dir(run_path())
        allowed = {"", "yes", "no", "unsure"}
        incoming = {r.get("id"): r for r in request.get_json()["rows"]}
        rows = read_review(directory, records)
        for row in rows:
            update = incoming.get(row["id"], {})
            for field in ("real_game", "gameplay_accurate"):
                if update.get(field) in allowed:
                    row[field] = update[field]
            row["notes"] = str(update.get("notes", row["notes"]))
        with (directory / "review_sample.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return jsonify(tally=review_tally(rows))

    @app.post("/api/titles/merge")
    def merge():
        body = request.get_json()
        canonical = clean_title(body["target"])
        aliases = load_aliases()
        for key in body["keys"]:
            if key != canonical:
                aliases[key] = canonical
        for key, value in list(aliases.items()):
            if value in body["keys"] and value != canonical:
                aliases[key] = canonical
        save_aliases(aliases)
        return jsonify(inspect_payload())

    @app.post("/api/titles/ignore")
    def ignore():
        aliases = load_aliases()
        aliases.update({key: IGNORE for key in request.get_json()["keys"]})
        save_aliases(aliases)
        return jsonify(inspect_payload())

    @app.post("/api/titles/undo")
    def undo():
        aliases = load_aliases()
        aliases.pop(request.get_json()["key"], None)
        save_aliases(aliases)
        return jsonify(inspect_payload())

    @app.post("/api/export")
    def export():
        directory = write_outputs(run_path(), ALIASES_PATH)
        return jsonify(folder=str(directory), files=sorted(p.name for p in pathlib.Path(directory).iterdir()))

    @app.get("/")
    @app.get("/<path:path>")
    def static_files(path="index.html"):
        return send_from_directory(DIST, path if (DIST / path).is_file() else "index.html")

    return app


if __name__ == "__main__":
    os.chdir(ROOT)
    url = "http://127.0.0.1:8502"
    print(f"Synthetic Users is running at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    create_app().run(host="127.0.0.1", port=8502, threaded=True)

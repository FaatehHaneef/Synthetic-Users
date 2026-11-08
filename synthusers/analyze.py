"""Clean game titles, measure how varied the synthetic crowd is, compare with the paper's Table 6."""
import collections
import csv
import json
import math
import pathlib
import random
import re
import unicodedata

from .generate import read_records

ALIASES_PATH = pathlib.Path("data/aliases.json")
RESULTS_DIR = pathlib.Path("results")
IGNORE = "__ignore__"
REVIEW_PER_GROUP = 10
COMPARABLE_MIN_MENTIONS = 150

# Table 6 of the paper: the listed counts, then "... and N other games" with their mentions.
PAPER_TABLE6 = {
    "Real people": {
        "listed": [10, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 3, 3], "other_games": 97, "other_mentions": 113,
        "top_game": "The Legend of Zelda: BOTW",
    },
    "GPT-3 davinci": {
        "listed": [44, 12, 8, 7, 6, 5, 5, 3, 3, 3, 2, 2, 2], "other_games": 65, "other_mentions": 69,
        "top_game": "Journey",
    },
    "GPT-3 text-davinci-002": {
        "listed": [151, 5, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1], "other_games": 10, "other_mentions": 10,
        "top_game": "Journey",
    },
}
PAPER_WORDS = {"Real people": 81.38, "GPT-3 davinci": 142.06}  # Experiment 1 stimuli, section 4.1


def paper_baselines():
    """OUR arithmetic on the authors' Table 6."""
    baselines = {}
    for name, row in PAPER_TABLE6.items():
        mentions = sum(row["listed"]) + row["other_mentions"]
        distinct = len(row["listed"]) + row["other_games"]
        baselines[name] = {
            "mentions": mentions,
            "distinct": distinct,
            "distinct_per_100": 100 * distinct / mentions,
            "top_game": row["top_game"],
            "top1_share": 100 * row["listed"][0] / mentions,
            "top3_share": 100 * sum(row["listed"][:3]) / mentions,
        }
    return baselines


PAPER_BASELINES = paper_baselines()

_PREFIXES = re.compile(
    r"^(?:the title(?: of the game)? (?:is|was)|title\s*:|it'?s called|it was called|it is called|"
    r"the game (?:i am|i'm) referring to is|the game (?:is|was)(?: called| titled| named)?|"
    r"i think(?: it was)?(?: called)?|that would be|that was|it was|it is|it'?s)\s+",
    re.I,
)
_NON_TITLE = re.compile(
    r"(?:do ?n'?t|do not|can'?t|cannot|could ?n'?t) (?:remember|recall)|not sure|no idea|^unknown$|^n/?a$|forgot|^none$", re.I
)


def strip_lead_in(raw):
    """Remove phrases like 'The game is called', keeping the title as written."""
    text = (raw or "").replace("’", "'").strip().strip("*_`\"“”' ")
    previous = None
    while previous != text:
        previous = text
        text = _PREFIXES.sub("", text).strip().strip("*_`\"“”' ")
    return text


def clean_title(raw):
    """Reduce a title to a comparison form. Automatic and imperfect, the aliases file fixes the rest."""
    text = unicodedata.normalize("NFKD", strip_lead_in(raw))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^the ", "", text)


def load_aliases(path=ALIASES_PATH):
    path = pathlib.Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_aliases(aliases, path=ALIASES_PATH):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(aliases.items())), indent=2, ensure_ascii=False), encoding="utf-8")


def canonical_title(raw, aliases):
    """Return the title key, or None if the response names no usable game."""
    if _NON_TITLE.search(raw or ""):
        return None
    key = clean_title(raw)
    if not key:
        return None
    key = aliases.get(key, key)
    return None if key == IGNORE else key


def wilson_interval(k, n, z=1.96):
    """95% interval for a share, in percent."""
    if not n:
        return (0.0, 0.0)
    p = k / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (100 * max(0.0, centre - margin), 100 * min(1.0, centre + margin))


def compute_metrics(records, aliases):
    """Metrics for one group of valid records."""
    counts = collections.Counter()
    display = collections.defaultdict(collections.Counter)
    ignored = 0
    for record in records:
        key = canonical_title(record["title_raw"], aliases)
        if key is None:
            ignored += 1
            continue
        counts[key] += 1
        display[key][strip_lead_in(record["title_raw"]).strip(" .")] += 1
    mentions = sum(counts.values())
    ranked = counts.most_common()
    names = {key: display[key].most_common(1)[0][0] for key in counts}
    top_count = ranked[0][1] if ranked else 0
    entropy = -sum((c / mentions) * math.log2(c / mentions) for c in counts.values()) if mentions else 0.0
    low, high = wilson_interval(top_count, mentions)
    return {
        "responses": len(records),
        "mentions": mentions,
        "ignored": ignored,
        "distinct": len(counts),
        "distinct_per_100": 100 * len(counts) / mentions if mentions else 0.0,
        "top_game": names[ranked[0][0]] if ranked else "",
        "top1_share": 100 * top_count / mentions if mentions else 0.0,
        "top1_low": low,
        "top1_high": high,
        "top3_share": 100 * sum(c for _, c in ranked[:3]) / mentions if mentions else 0.0,
        "entropy_bits": entropy,
        "mean_words": sum(r["words"] for r in records) / len(records) if records else 0.0,
        "comparable": mentions >= COMPARABLE_MIN_MENTIONS,
        "ranked": [{"key": key, "title": names[key], "count": count} for key, count in ranked],
    }


def analyze_records(records, aliases):
    valid = [r for r in records if r["status"] == "valid"]
    groups = {}
    for condition in ("default", "persona"):
        subset = [r for r in valid if r["condition"] == condition]
        if subset:
            groups[condition] = compute_metrics(subset, aliases)
    discards = collections.Counter(r["status"] for r in records if r["status"] != "valid")
    return {
        "provider": records[0]["provider"] if records else "",
        "model": records[0]["model"] if records else "",
        "is_fake_data": bool(records) and records[0]["provider"] == "fake",
        "requests": len({r["request_id"] for r in records}),
        "keys_used": sorted({r["key_number"] for r in records}),
        "discards": dict(discards),
        "groups": groups,
    }


def persona_top_titles(records, aliases):
    """For each persona, its most common titles. For reading stereotype patterns."""
    rows = []
    personas = sorted({(r["persona_id"], r["persona"]) for r in records if r["status"] == "valid" and r["condition"] == "persona"})
    for persona_id, persona in personas:
        subset = [r for r in records if r["status"] == "valid" and r["persona_id"] == persona_id]
        metrics = compute_metrics(subset, aliases)
        top = ", ".join(f"{g['title']} ({g['count']})" for g in metrics["ranked"][:3])
        rows.append({"persona": persona, "responses": metrics["responses"], "top_titles": top})
    return rows


# ----- review of sampled answers ---------------------------------------------

REVIEW_FIELDS = ["id", "condition", "persona", "title", "answer", "real_game", "gameplay_accurate", "notes"]


def results_dir(run_path):
    return RESULTS_DIR / pathlib.Path(run_path).stem


def ensure_review_sample(records, directory):
    """Create the review sheet once. Never overwrites what a person has filled in."""
    path = pathlib.Path(directory) / "review_sample.csv"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    picker = random.Random(2023)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for condition in ("default", "persona"):
            subset = [r for r in records if r["status"] == "valid" and r["condition"] == condition]
            for record in picker.sample(subset, min(REVIEW_PER_GROUP, len(subset))):
                writer.writerow({"id": record["id"], "condition": condition, "persona": record["persona"] or "",
                                 "title": record["title_raw"], "answer": record["answer"],
                                 "real_game": "", "gameplay_accurate": "", "notes": ""})
    return path


def review_tally(rows):
    """Count the human review. 'no' means a person checked and it was wrong."""
    rows = list(rows)
    checked = [r for r in rows if str(r.get("gameplay_accurate") or "").strip() in ("yes", "no", "unsure")]
    return {
        "total": len(rows),
        "checked": len(checked),
        "inaccurate": sum(str(r.get("gameplay_accurate")).strip() == "no" for r in checked),
        "unsure": sum(str(r.get("gameplay_accurate")).strip() == "unsure" for r in checked),
        "not_real_game": sum(str(r.get("real_game") or "").strip() == "no" for r in rows),
    }


# ----- outputs ----------------------------------------------------------------


def chart_rows(analysis, measure):
    """Rows for a chart or table: the paper's three groups, then our groups."""
    rows = [{"label": f"{name} (paper)", "value": base[measure], "ours": False} for name, base in PAPER_BASELINES.items()]
    names = {"default": "plain prompt", "persona": "with persona"}
    for condition, metrics in analysis["groups"].items():
        rows.append({"label": f"{analysis['model']}, {names[condition]} (our run)", "value": metrics[measure], "ours": True})
    return rows


def chart_alt_text(analysis, measure, label):
    parts = "; ".join(f"{row['label']}: {row['value']:.1f}" for row in chart_rows(analysis, measure))
    return f"{label}. {parts}."


LIGHT_CHART = {"surface": "#ffffff", "ink": "#111111", "muted": "#333333", "faint": "#555555", "grid": "#e3e5e8", "axis": "#b5b9bf", "ours": "#1f5fbf", "paper": "#8b9099"}
DARK_CHART = {"surface": "#0a0b12", "ink": "#f4f5f8", "muted": "#c4c8d0", "faint": "#9aa0ab", "grid": "#23262f", "axis": "#4a4f5b", "ours": "#38bdf8", "paper": "#8b9099"}


def save_chart(analysis, measure, title, xlabel, path, palette=LIGHT_CHART):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = list(reversed(chart_rows(analysis, measure)))
    figure, axis = plt.subplots(figsize=(11, 0.75 * len(rows) + 2), dpi=150)
    axis.set_facecolor(palette["surface"])
    values = [row["value"] for row in rows]
    colors = [palette["ours"] if row["ours"] else palette["paper"] for row in rows]
    hatches = ["" if row["ours"] else "///" for row in rows]
    bars = axis.barh([row["label"] for row in rows], values, color=colors, height=0.55, edgecolor=palette["surface"], linewidth=1)
    for bar, hatch, value in zip(bars, hatches, values):
        bar.set_hatch(hatch)
        axis.text(value + max(values) * 0.012, bar.get_y() + bar.get_height() / 2, f"{value:.1f}",
                  va="center", fontsize=15, color=palette["ink"], fontweight="bold")
    axis.set_xlim(0, max(max(values) * 1.12, 1))
    figure.suptitle(title, x=0.01, ha="left", fontsize=18, color=palette["ink"])
    axis.set_xlabel(xlabel, fontsize=14, color=palette["muted"])
    axis.tick_params(axis="y", labelsize=14, length=0, colors=palette["ink"])
    axis.tick_params(axis="x", labelsize=12, colors=palette["faint"])
    axis.xaxis.grid(True, color=palette["grid"], linewidth=0.8)
    axis.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(palette["axis"])
    note = "Hatched grey: the paper's Table 6 (GPT-3, 2022). Solid: our run. Simulated participants."
    if analysis["is_fake_data"]:
        note = "FAKE DEMO DATA, offline test only. " + note
    figure.text(0.01, 0.01, note, fontsize=11.5, color=palette["muted"])
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=palette["surface"])
    plt.close(figure)
    return path


CHARTS = {
    "top1_share": ("How much of the crowd named the single most common game", "Share of game mentions (%)"),
    "distinct_per_100": ("How many different games appeared per 100 mentions", "Different games per 100 mentions"),
}


def write_outputs(run_path, aliases_path=ALIASES_PATH):
    """Write everything the slides and guide use. Returns the output directory."""
    records = read_records(run_path)
    aliases = load_aliases(aliases_path)
    analysis = analyze_records(records, aliases)
    directory = results_dir(run_path)
    directory.mkdir(parents=True, exist_ok=True)

    with (directory / "titles_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["condition", "title", "key", "count"])
        for condition, metrics in analysis["groups"].items():
            for row in metrics["ranked"]:
                writer.writerow([condition, row["title"], row["key"], row["count"]])

    with (directory / "persona_titles.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["persona", "responses", "top_titles"])
        writer.writeheader()
        writer.writerows(persona_top_titles(records, aliases))

    for measure, (title, xlabel) in CHARTS.items():
        if analysis["groups"]:
            save_chart(analysis, measure, title, xlabel, directory / f"{measure}.png")
            save_chart(analysis, measure, title, xlabel, directory / f"{measure}_dark.png", DARK_CHART)

    review_path = ensure_review_sample(records, directory)
    with review_path.open(newline="", encoding="utf-8") as handle:
        tally = review_tally(csv.DictReader(handle))

    summary = {
        **{k: v for k, v in analysis.items() if k != "groups"},
        "note": "Simulated participants, not user evidence. Illustrates Hamalainen et al. (CHI '23), does not reproduce it.",
        "groups": {c: {k: v for k, v in m.items() if k != "ranked"} for c, m in analysis["groups"].items()},
        "top_titles": {c: m["ranked"][:15] for c, m in analysis["groups"].items()},
        "paper_baselines": PAPER_BASELINES,
        "paper_words": PAPER_WORDS,
        "review": tally,
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return directory

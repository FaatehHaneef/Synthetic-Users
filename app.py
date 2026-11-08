"""Local interface for the diversity probe. Run with: streamlit run app.py"""
import csv
import pathlib

import pandas as pd
import streamlit as st

from synthusers.analyze import (ALIASES_PATH, CHARTS, IGNORE, PAPER_BASELINES, PAPER_WORDS, analyze_records, chart_alt_text,
                                chart_rows, clean_title, ensure_review_sample, load_aliases, persona_top_titles, results_dir,
                                review_tally, save_aliases, save_chart, write_outputs)
from synthusers.generate import (DEFAULT_MODEL, KEY_STATE_PATH, RUNS_DIR, ApiError, GeminiProvider, estimate_requests, make_provider,
                                 probe_candidates, read_records, run_generation)
from synthusers.keys import AllKeysExhausted, KeyPool, load_keys
from synthusers.prompts import PERSONAS, SYSTEM_INSTRUCTION, build_prompt
from synthusers.themes import THEMES, tag_answer, theme_counts

CONDITION_NAMES = {"default": "Plain prompt", "persona": "With persona"}

st.set_page_config(page_title="Synthetic Participants Probe", layout="wide")
st.markdown(
    """
    <style>
    html, body, [class*="st-"], p, li, label { font-size: 19px; }
    h1 { font-size: 2.2rem !important; } h2 { font-size: 1.7rem !important; } h3 { font-size: 1.35rem !important; }
    [data-baseweb="tab"] p { font-size: 20px; font-weight: 600; }
    :focus-visible { outline: 3px solid #1f5fbf !important; outline-offset: 2px; }
    .banner { background: #111111; color: #ffffff; padding: 12px 18px; border-radius: 6px; font-weight: 600; margin-bottom: 10px; }
    .fake { background: #ffffff; color: #8a1c00; border: 3px solid #8a1c00; padding: 10px 18px; border-radius: 6px; font-weight: 700; margin-bottom: 10px; }
    .tag { display: inline-block; border: 1px solid #333333; border-radius: 4px; padding: 0 8px; margin-right: 6px; font-size: 16px; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="banner" role="note">SIMULATED PARTICIPANTS, not user evidence. '
    "Illustrates Hämäläinen et al. (CHI '23), does not reproduce it.</div>",
    unsafe_allow_html=True,
)
st.title("Can an AI crowd be as varied as real people?")


def list_runs():
    return sorted(path.stem for path in RUNS_DIR.glob("*.jsonl")) if RUNS_DIR.exists() else []


def read_review(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


if "next_run" in st.session_state:
    st.session_state["run_name"] = st.session_state.pop("next_run")

runs = list_runs()
selected = st.selectbox("Saved run shown on every screen", runs, key="run_name", index=None if not runs else 0,
                        placeholder="No saved run yet, generate one on the Setup screen")
records, analysis, aliases = [], None, load_aliases()
run_path = RUNS_DIR / f"{selected}.jsonl" if selected else None
if run_path and run_path.exists():
    records = read_records(run_path)
    analysis = analyze_records(records, aliases)
    if analysis["is_fake_data"]:
        st.markdown('<div class="fake" role="alert">FAKE DEMO DATA from the offline test provider. '
                    "Do not use these numbers anywhere.</div>", unsafe_allow_html=True)

setup, works, fails, titles, export = st.tabs(["1. Setup", "2. Scenario 1: Works", "3. Scenario 2: Fails", "4. Clean titles", "5. Export"])


def need_data():
    if not analysis or not analysis["groups"]:
        st.info("Choose or generate a run with valid interviews on the Setup screen.")
        return True
    return False


# ----- 1. setup ---------------------------------------------------------------
with setup:
    st.header("Generate synthetic interviews")
    left, right = st.columns(2)
    with left:
        provider_name = st.selectbox("Provider", ["fake", "gemini"], format_func=lambda p: {"fake": "Fake (offline test)", "gemini": "Gemini (uses real quota)"}[p])
        model = st.text_input("Model", DEFAULT_MODEL, disabled=provider_name == "fake")
        new_name = st.text_input("Run name (an existing name continues that run)", "fake-demo" if provider_name == "fake" else "gemini-main")
    with right:
        n = st.number_input("Participants per group", 1, 500, 178, help="The paper used 178.")
        candidates = st.number_input("Answers per request (Gemini 3.6 Flash only allows 1)", 1, 8, 1)
        rpm = st.number_input("Requests per minute per key", 1, 300, 20, help="Waits automatically if Google says this is too fast.")
        conditions = st.multiselect("Groups", ["default", "persona"], ["default", "persona"], format_func=CONDITION_NAMES.get)

    st.write(f"This needs about **{estimate_requests(n, conditions, candidates) if conditions else 0} requests** if every answer passes the quality rules.")
    if n < 150:
        st.warning("Under about 150 participants, 'different games per 100 mentions' looks better than it is, because small groups repeat less. Compare only the top game's share.")

    if provider_name == "gemini":
        keys = load_keys()
        if keys:
            st.subheader(f"{len(keys)} key(s) loaded")
            st.dataframe(pd.DataFrame(KeyPool(keys, model, KEY_STATE_PATH).status()), hide_index=True)
        else:
            st.error("No keys found. Add GEMINI_KEY_1=... to a .env file in this folder.")

    run_clicked = st.button("Generate", type="primary", disabled=not conditions)
    probe_clicked = provider_name == "gemini" and st.button("Test one request")
    if run_clicked or probe_clicked:
        log = st.empty()
        events = []

        def on_event(message):
            events.append(message)
            log.text("\n".join(events[-6:]))

        try:
            if probe_clicked:
                st.json(probe_candidates(GeminiProvider(load_keys(), model, on_event=on_event), candidates))
            else:
                bar = st.progress(0.0, "Starting")
                provider = make_provider(provider_name, model, rpm=rpm, on_event=on_event)
                summary = run_generation(
                    provider, RUNS_DIR / f"{new_name}.jsonl", n, conditions, candidates, on_event=on_event,
                    on_progress=lambda done, target, count: bar.progress(done / target, f"{done} of {target} interviews, {count} requests"),
                )
                st.session_state["next_run"] = new_name
                st.session_state["last_summary"] = summary
                st.rerun()
        except (ApiError, AllKeysExhausted) as error:
            st.error(str(error))

    if "last_summary" in st.session_state:
        summary = st.session_state["last_summary"]
        reasons = {"complete": "Finished.", "all_keys_exhausted": "All keys are out of quota today. Saved, press Generate after the daily reset to continue.",
                   "request_cap": "Stopped at the request cap. Saved, press Generate to continue.", "no_valid_replies": "Stopped because replies were unusable.", "api_error": "Stopped on an error from Google, see the message above. Saved."}
        st.success(f"{reasons[summary['stopped']]} {summary['valid']} of {summary['target']} interviews, {summary['requests']} requests.")

    with st.expander("See the exact prompt (paper's Table 1, with our additions)"):
        st.markdown("**Interview prompt, verbatim from the paper**")
        st.code(build_prompt(), language=None, wrap_lines=True)
        st.markdown("**Our addition: instruction so a chat model continues the transcript and gives the title in the same reply**")
        st.code(SYSTEM_INSTRUCTION, language=None, wrap_lines=True)
        st.markdown("**Our addition: one of these lines goes after the first line, in the persona group only**")
        st.code("\n".join(f"(Participant background: {p}.)" for p in PERSONAS), language=None, wrap_lines=True)

# ----- 2. works ---------------------------------------------------------------
with works:
    st.header("The answers read like real interviews")
    st.markdown("**Authors' proposed use:** pilot-testing and debugging analysis pipelines before recruiting real people (§7.1).  \n"
                "**Our demo:** an illustration of that use, on simulated answers.")
    if not need_data():
        valid = [r for r in records if r["status"] == "valid"]
        condition = st.radio("Group", list(analysis["groups"]), format_func=CONDITION_NAMES.get, horizontal=True, key="works_group")
        subset = [r for r in valid if r["condition"] == condition]
        st.subheader("Themes found")
        st.dataframe(pd.DataFrame(theme_counts(r["answer"] for r in subset), columns=["Theme", "Responses tagged"]), hide_index=True)
        with st.expander("How themes are tagged: whole-word keyword matches, nothing else"):
            for theme, words in THEMES.items():
                st.markdown(f"**{theme}:** {', '.join(words)}")
        st.subheader("Interviews")
        shown = st.slider("How many to show", 1, min(30, len(subset)), min(6, len(subset))) if len(subset) > 1 else 1
        for record in subset[:shown]:
            with st.container(border=True):
                st.markdown(f"**Game named: {record['title_raw']}**" + (f"  \nBackground: {record['persona']}" if record["persona"] else ""))
                st.write(record["answer"])
                tags = tag_answer(record["answer"])
                st.markdown("Themes: " + ("".join(f'<span class="tag">{t}</span>' for t in tags) or "none"), unsafe_allow_html=True)

# ----- 3. fails ---------------------------------------------------------------
with fails:
    st.header("But does the crowd have real variety?")
    if not need_data():
        if not all(g["comparable"] for g in analysis["groups"].values()):
            st.warning("This run has fewer than 150 game mentions in at least one group, so 'different games per 100' is not comparable with the paper's 179. Use the top game's share.")
        table = []
        for name, base in PAPER_BASELINES.items():
            table.append({"Group": f"{name} (paper, Table 6)", "Mentions": base["mentions"], "Different games": base["distinct"],
                          "Different per 100": round(base["distinct_per_100"], 1), "Top game": base["top_game"],
                          "Top game share %": round(base["top1_share"], 1), "Top 3 share %": round(base["top3_share"], 1)})
        for condition, group in analysis["groups"].items():
            table.append({"Group": f"{analysis['model']}, {CONDITION_NAMES[condition].lower()} (our run)", "Mentions": group["mentions"], "Different games": group["distinct"],
                          "Different per 100": round(group["distinct_per_100"], 1), "Top game": group["top_game"],
                          "Top game share %": round(group["top1_share"], 1), "Top 3 share %": round(group["top3_share"], 1)})
        st.dataframe(pd.DataFrame(table), hide_index=True)
        st.caption("Paper rows are our arithmetic on the authors' Table 6 (GPT-3, 2022). Our rows are one model on one question.")
        for condition, group in analysis["groups"].items():
            st.markdown(f"**{CONDITION_NAMES[condition]}:** top game share {group['top1_share']:.1f}%, 95% interval {group['top1_low']:.1f} to {group['top1_high']:.1f}%.")

        directory = results_dir(run_path)
        for measure, (title, xlabel) in CHARTS.items():
            path = save_chart(analysis, measure, title, xlabel, directory / f"{measure}.png")
            st.image(str(path))
            st.caption("Chart description: " + chart_alt_text(analysis, measure, title))

        st.subheader("Most mentioned games")
        columns = st.columns(len(analysis["groups"]))
        for column, (condition, group) in zip(columns, analysis["groups"].items()):
            with column:
                st.markdown(f"**{CONDITION_NAMES[condition]}**")
                st.dataframe(pd.DataFrame(group["ranked"][:15])[["title", "count"]].rename(columns={"title": "Game", "count": "Mentions"}), hide_index=True)
        if "persona" in analysis["groups"]:
            with st.expander("Top games per persona (check for stereotyped patterns)"):
                st.dataframe(pd.DataFrame(persona_top_titles(records, aliases)), hide_index=True)

        st.subheader("Response length")
        lengths = [{"Group": f"{name} (paper, Exp 1 stimuli)", "Mean words": words} for name, words in PAPER_WORDS.items()]
        lengths += [{"Group": f"{CONDITION_NAMES[c]} (our run)", "Mean words": round(g["mean_words"], 1)} for c, g in analysis["groups"].items()]
        st.dataframe(pd.DataFrame(lengths), hide_index=True)
        st.caption("Our observation: the paper's GPT-3 texts were longer than the human ones, which may be a confound in Experiment 1.")

        st.subheader("Hallucination review, done by a person")
        review_path = ensure_review_sample(records, directory)
        rows = read_review(review_path)
        options = ["", "yes", "no", "unsure"]
        edited = st.data_editor(
            pd.DataFrame(rows).fillna(""), hide_index=True, disabled=["id", "condition", "persona", "title", "answer"], key=f"review_{selected}",
            column_config={"id": None,
                           "real_game": st.column_config.SelectboxColumn("Is the game real?", options=options),
                           "gameplay_accurate": st.column_config.SelectboxColumn("Gameplay accurate?", options=options),
                           "notes": st.column_config.TextColumn("Notes")},
        )
        if st.button("Save review"):
            edited.to_csv(review_path, index=False, encoding="utf-8")
            st.success("Saved.")
        tally = review_tally(edited.to_dict("records"))
        st.markdown(f"**{tally['inaccurate']} of {tally['checked']} reviewed responses had inaccurate gameplay** "
                    f"({tally['unsure']} unsure, {tally['not_real_game']} named a game that is not real, {tally['total'] - tally['checked']} not reviewed yet). Our observation.")

# ----- 4. titles --------------------------------------------------------------
with titles:
    st.header("Clean up game titles")
    st.write("Cleaning is automatic and imperfect. Merge titles that mean the same game. Changes apply to every screen.")
    if not need_data():
        counts = {}
        names = {}
        for group in analysis["groups"].values():
            for row in group["ranked"]:
                counts[row["key"]] = counts.get(row["key"], 0) + row["count"]
                names.setdefault(row["key"], row["title"])
        ordered = sorted(counts, key=lambda k: -counts[k])
        st.dataframe(pd.DataFrame([{"Title": names[k], "Comparison form": k, "Mentions": counts[k]} for k in ordered]), hide_index=True)
        chosen = st.multiselect("Titles to change", ordered, format_func=lambda k: f"{names[k]} ({counts[k]})")
        target = st.text_input("Merge into this title")
        merge_col, ignore_col = st.columns(2)
        if merge_col.button("Merge titles", disabled=not (chosen and target.strip())):
            canonical = clean_title(target)
            for key in chosen:
                if key != canonical:
                    aliases[key] = canonical
            for key, value in list(aliases.items()):
                if value in chosen and value != canonical:
                    aliases[key] = canonical
            save_aliases(aliases)
            st.rerun()
        if ignore_col.button("Exclude: not a specific published game", disabled=not chosen):
            for key in chosen:
                aliases[key] = IGNORE
            save_aliases(aliases)
            st.rerun()
    if aliases:
        st.subheader("Current merges")
        st.dataframe(pd.DataFrame([{"From": k, "To": v} for k, v in aliases.items()]), hide_index=True)
        remove = st.selectbox("Undo a merge", list(aliases), index=None, placeholder="Choose one")
        if st.button("Undo", disabled=remove is None):
            aliases.pop(remove)
            save_aliases(aliases)
            st.rerun()
    st.caption(f"Saved in {ALIASES_PATH}")

# ----- 5. export --------------------------------------------------------------
with export:
    st.header("Export for the slides and guide")
    if not need_data():
        st.write(f"Writes CSV files, charts and summary.json to `{results_dir(run_path)}`.")
        if st.button("Export results", type="primary"):
            directory = write_outputs(run_path)
            st.success("Written: " + ", ".join(sorted(p.name for p in pathlib.Path(directory).iterdir())))

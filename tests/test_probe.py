"""Offline tests. No network, no keys."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from synthusers.analyze import (IGNORE, PAPER_BASELINES, analyze_records, canonical_title, clean_title, compute_metrics,
                                ensure_review_sample, review_tally, wilson_interval)
from synthusers.generate import (FakeProvider, GeminiProvider, Job, classify_429, estimate_requests, parse_reply,
                                 persona_targets, plan_next_job, quality_status, read_records, run_generation)
from synthusers.keys import AllKeysExhausted, KeyPool, load_keys
from synthusers.prompts import PERSONAS, PROMPT_1, build_prompt
from synthusers.themes import tag_answer

GOOD_REPLY = {"candidates": [{"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}]}
DAILY = {"error": {"message": "quota", "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}
MINUTE = {"error": {"message": "quota", "details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]}, {"retryDelay": "30s"}]}}


class Response:
    def __init__(self, status_code, payload):
        self.status_code, self.payload, self.text = status_code, payload, json.dumps(payload)

    def json(self):
        return self.payload


class Session:
    def __init__(self, script):
        self.script, self.keys = list(script), []

    def post(self, url, headers, json, timeout):
        self.keys.append(headers["x-goog-api-key"])
        return self.script.pop(0)


def provider(script, keys=("k1", "k2", "k3"), events=None):
    sleeps = []
    instance = GeminiProvider(list(keys), "m", state_path=None, session=Session(script), sleep=sleeps.append,
                              clock=lambda: 0.0, on_event=(events.append if events is not None else None))
    instance.sleeps = sleeps
    return instance


def test_paper_baselines_match_table6():
    assert PAPER_BASELINES["Real people"]["mentions"] == 179
    assert PAPER_BASELINES["Real people"]["distinct"] == 110
    assert round(PAPER_BASELINES["Real people"]["top1_share"], 1) == 5.6
    assert PAPER_BASELINES["GPT-3 davinci"]["mentions"] == 171
    assert PAPER_BASELINES["GPT-3 davinci"]["distinct"] == 78
    assert round(PAPER_BASELINES["GPT-3 davinci"]["top1_share"], 1) == 25.7
    assert PAPER_BASELINES["GPT-3 text-davinci-002"]["mentions"] == 181
    assert PAPER_BASELINES["GPT-3 text-davinci-002"]["distinct"] == 23
    assert round(PAPER_BASELINES["GPT-3 text-davinci-002"]["top1_share"], 1) == 83.4


def test_prompt_is_verbatim_and_persona_goes_after_first_line():
    assert PROMPT_1.endswith("Participant:")
    assert "in at least 50 words" in PROMPT_1
    assert build_prompt() == PROMPT_1
    lines = build_prompt("a test person").split("\n")
    assert lines[1] == "(Participant background: a test person.)"
    assert "\n".join([lines[0]] + lines[2:]) == PROMPT_1


@pytest.mark.parametrize("raw,expected", [
    ("Journey", "journey"), ("journey.", "journey"), ('"Journey"', "journey"), ("**Journey**", "journey"),
    ("The title of the game is Journey.", "journey"), ("It's called Flower", "flower"),
    ("NieR: Automata", "nier automata"), ("Nier Automata", "nier automata"), ("Pokémon Red", "pokemon red"),
    ("The Last of Us", "last of us"), ("Journey (2012)", "journey"), ("Papers, Please", "papers please"),
    ("It Takes Two", "it takes two"), ("The game I am referring to is Journey", "journey"),
    ("The game is titled Gris", "gris"), ("The game is called Gris", "gris"),
])
def test_clean_title(raw, expected):
    assert clean_title(raw) == expected


def test_aliases_and_non_titles():
    aliases = {"breath of the wild": "legend of zelda breath of the wild", "fake game": IGNORE}
    assert canonical_title("Breath of the Wild", aliases) == "legend of zelda breath of the wild"
    assert canonical_title("Fake Game", aliases) is None
    assert canonical_title("I can't remember the name", {}) is None
    assert canonical_title("", {}) is None


def record(title, words=50, condition="default", status="valid", provider_name="fake"):
    return {"title_raw": title, "words": words, "condition": condition, "status": status, "persona_id": None,
            "persona": None, "id": title, "request_id": title, "provider": provider_name, "model": "m", "key_number": 1, "answer": "a"}


def test_metrics():
    metrics = compute_metrics([record("Journey"), record("journey."), record("Flower"), record("Bioshock")], {})
    assert metrics["mentions"] == 4 and metrics["distinct"] == 3
    assert metrics["top1_share"] == 50.0 and metrics["top3_share"] == 100.0
    assert metrics["entropy_bits"] == pytest.approx(1.5)
    assert metrics["distinct_per_100"] == 75.0
    assert metrics["comparable"] is False


def test_analysis_ignores_discards_and_flags_fake():
    analysis = analyze_records([record("Journey"), record("X", status="too_short")], {})
    assert analysis["groups"]["default"]["responses"] == 1
    assert analysis["discards"] == {"too_short": 1}
    assert analysis["is_fake_data"] is True


def test_wilson():
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(40.4, abs=0.2) and high == pytest.approx(59.6, abs=0.2)


def test_parse_reply():
    answer, title = parse_reply("I loved it a lot.\n\nResearcher: What is the title of the game?\nParticipant: Journey")
    assert (answer, title) == ("I loved it a lot.", "Journey")
    assert parse_reply("Participant: **Text**\nResearcher: x\nParticipant: Game")[0] == "Text"
    assert parse_reply("no title here") == ("no title here", "")


def test_quality_rules_from_the_paper():
    assert quality_status("too few words", "Game") == "too_short"
    long_text = "one two three four five six seven eight nine ten eleven"
    assert quality_status(long_text, "Game") == "valid"
    assert quality_status(long_text, "") == "no_title"
    assert quality_status("this exact phrase repeats this exact phrase repeats and then it ends here ok", "G") == "repetition"


def test_planning():
    assert sum(persona_targets(178)) == 178 and len(persona_targets(178)) == len(PERSONAS)
    assert plan_next_job({}, 16, ["default", "persona"], 8) == Job("default", None, 8)
    assert plan_next_job({("default", None): 16}, 16, ["default"], 8) is None
    job = plan_next_job({("default", None): 16}, 16, ["default", "persona"], 8)
    assert job.condition == "persona" and job.n == 2
    assert estimate_requests(178, ["default", "persona"], 8) == 23 + 30


def test_classify_429():
    assert classify_429(DAILY) == ("daily", None)
    assert classify_429(MINUTE) == ("minute", 30.0)


def test_daily_quota_falls_back_to_next_key():
    events = []
    instance = provider([Response(429, DAILY), Response(200, GOOD_REPLY)], events=events)
    result = instance.generate("p", "s", 1)
    assert result.key_number == 2 and instance.session.keys == ["k1", "k2"]
    assert "Key 1" in events[0]
    assert instance.pool.status()[0]["status"] == "out of quota today"


def test_minute_limit_waits_on_same_key():
    instance = provider([Response(429, MINUTE), Response(200, GOOD_REPLY)])
    assert instance.generate("p", "s", 1).key_number == 1
    assert instance.session.keys == ["k1", "k1"] and 30.0 in instance.sleeps


def test_all_keys_out_raises():
    instance = provider([Response(429, DAILY)] * 3)
    with pytest.raises(AllKeysExhausted):
        instance.generate("p", "s", 1)


def test_invalid_key_is_skipped_and_never_logged():
    events = []
    bad = {"error": {"message": "API key not valid: k1"}}
    instance = provider([Response(400, bad), Response(200, GOOD_REPLY)], events=events)
    assert instance.generate("p", "s", 1).key_number == 2
    assert not any("k1" in event for event in events)


def test_key_pool_resets_each_pacific_day(tmp_path):
    day = ["2026-01-01"]
    pool = KeyPool(["a"], "m", tmp_path / "state.json", today=lambda: day[0])
    pool.mark_exhausted(1)
    with pytest.raises(AllKeysExhausted):
        pool.current()
    reloaded = KeyPool(["a"], "m", tmp_path / "state.json", today=lambda: day[0])
    with pytest.raises(AllKeysExhausted):
        reloaded.current()
    day[0] = "2026-01-02"
    assert reloaded.current() == (1, "a")


def test_load_keys_any_count_in_numeric_order(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_KEY_10=j\nGEMINI_KEY_2=b\n# note\nGEMINI_KEY_1='a'\n", encoding="utf-8")
    assert load_keys(env, environ={}) == ["a", "b", "j"]


def test_fake_run_reaches_target_and_resumes(tmp_path):
    path = tmp_path / "run.jsonl"
    first = run_generation(FakeProvider(), path, 20, ["default", "persona"], 8, max_requests=2)
    assert first["stopped"] == "request_cap"
    second = run_generation(FakeProvider(seed=8), path, 20, ["default", "persona"], 8)
    assert second["stopped"] == "complete" and second["valid"] == 40
    records = read_records(path)
    assert sum(r["status"] == "valid" and r["condition"] == "default" for r in records) == 20
    assert all("FAKE" in r["answer"] for r in records if r["status"] == "valid")


def test_run_stops_cleanly_when_keys_run_out(tmp_path):
    reply = {"candidates": [{"content": {"parts": [{"text": "one two three four five six seven eight nine ten eleven twelve\nResearcher: t\nParticipant: Journey"}]}, "finishReason": "STOP"}]}
    instance = provider([Response(200, reply), Response(429, DAILY), Response(429, DAILY), Response(429, DAILY)])
    summary = run_generation(instance, tmp_path / "r.jsonl", 10, ["default"], 1)
    assert summary["stopped"] == "all_keys_exhausted" and summary["valid"] == 1


def test_unrecognised_limit_error_stops_and_is_logged_without_keys(tmp_path):
    unknown = {"error": {"message": "something new for k1"}}
    instance = provider([Response(429, unknown)])
    instance.log_path = tmp_path / "log.jsonl"
    summary = run_generation(instance, tmp_path / "r.jsonl", 2, ["default"], 1)
    assert summary["stopped"] == "api_error"
    log = instance.log_path.read_text(encoding="utf-8")
    assert '"status": 429' in log and "something new" in log and "k1" not in log


def test_run_refuses_to_mix_models(tmp_path):
    path = tmp_path / "r.jsonl"
    run_generation(FakeProvider(), path, 2, ["default"], 2)
    with pytest.raises(Exception, match="new run name"):
        run_generation(FakeProvider(model="other"), path, 2, ["default"], 2)


def test_review_sheet_is_not_overwritten(tmp_path):
    records = [dict(record(f"G{i}"), id=str(i)) for i in range(15)]
    path = ensure_review_sample(records, tmp_path)
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 11
    path.write_text("edited", encoding="utf-8")
    ensure_review_sample(records, tmp_path)
    assert path.read_text(encoding="utf-8") == "edited"


def test_review_tally():
    tally = review_tally([{"gameplay_accurate": "no", "real_game": "yes"}, {"gameplay_accurate": "yes", "real_game": "no"}, {"gameplay_accurate": ""}])
    assert tally == {"total": 3, "checked": 2, "inaccurate": 1, "unsure": 0, "not_real_game": 1}


def test_theme_tagger_matches_whole_words():
    assert "Story" in tag_answer("The story moved me")
    assert tag_answer("historyish") == []

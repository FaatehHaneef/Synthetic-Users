"""The local API, on a fake run in a temporary folder. No network, no keys."""
import json
import pathlib
import sys
import time

import pytest
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from server import create_app
from synthusers.generate import ApiError, FakeProvider, GeminiProvider, RUNS_DIR, run_generation
from synthusers.keys import AllKeysExhausted


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_generation(FakeProvider(), RUNS_DIR / "gemini-main.jsonl", 24, ["default", "persona"], 8)
    return tmp_path


class Failing:
    def __init__(self, error, after=0):
        self.error, self.after, self.fake = error, after, FakeProvider()
        self.pool = type("P", (), {"invalid": set(), "keys": ["a"]})()

    def generate(self, prompt, system, n):
        if self.after == 0:
            raise self.error
        self.after -= 1
        return self.fake.generate(prompt, system, n)


def run_live(make_provider, count=5):
    client = create_app(make_provider).test_client()
    job = client.post("/api/live", json={"count": count}).get_json()["id"]
    for _ in range(200):
        body = client.get(f"/api/live/{job}").get_json()
        if body["state"] == "done":
            return body
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_live_returns_cards_and_summary(workspace):
    body = run_live(FakeProvider, 5)
    assert len(body["items"]) == 5 and body["error"] is None
    assert body["summary"]["total"] == 5 and body["items"][0]["game"]


@pytest.mark.parametrize("error,message", [
    (AllKeysExhausted("x"), "API key quota exhausted."),
    (ApiError("raw detail 500", kind="busy"), "Google's servers didn't respond."),
    (ApiError("raw detail", kind="offline"), "No internet connection."),
    (ApiError("Gemini returned 400: secret detail"), "The request didn't go through. Try again."),
    (ValueError("boom"), "The request didn't go through. Try again."),
])
def test_failures_are_plain_sentences(workspace, error, message):
    assert run_live(lambda: Failing(error))["error"]["message"] == message


def test_all_keys_refused_message(workspace):
    provider = Failing(AllKeysExhausted("x"))
    provider.pool.invalid = {1}
    assert run_live(lambda: provider)["error"]["message"] == "These API keys were refused by Google."


def test_no_keys_at_all_reads_as_refused(workspace):
    def no_keys():
        raise AllKeysExhausted("none")

    assert run_live(no_keys)["error"]["message"] == "These API keys were refused by Google."


def test_partial_results_are_kept(workspace):
    body = run_live(lambda: Failing(AllKeysExhausted("x"), after=3), 5)
    assert len(body["items"]) == 3 and body["error"]["message"] == "API key quota exhausted."


def test_retry_budget_gives_up_with_busy(workspace):
    class Session:
        calls = 0

        def post(self, *args, **kwargs):
            Session.calls += 1
            return type("R", (), {"status_code": 503, "text": "{}", "json": lambda self: {}})()

    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    provider = GeminiProvider(["k"], "m", state_path=None, session=Session(), sleep=sleep, clock=lambda: now[0], retry_budget=25)
    with pytest.raises(ApiError) as caught:
        provider.generate("p", "s", 1)
    assert caught.value.kind == "busy" and Session.calls >= 2 and now[0] <= 26


def test_connection_failure_is_offline(workspace):
    class Session:
        def post(self, *args, **kwargs):
            raise requests.ConnectionError("no route")

    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    provider = GeminiProvider(["k"], "m", state_path=None, session=Session(), sleep=sleep, clock=lambda: now[0], retry_budget=25)
    with pytest.raises(ApiError) as caught:
        provider.generate("p", "s", 1)
    assert caught.value.kind == "offline"


def test_saved_endpoint(workspace):
    body = create_app(FakeProvider).test_client().get("/api/saved").get_json()
    assert set(body["groups"]) == {"default", "persona"} and body["human"]["share"] == 5.6
    assert len(body["personas"]) == 10


def test_inspect_review_titles_export(workspace):
    client = create_app(FakeProvider).test_client()
    data = client.get("/api/inspect").get_json()
    assert data["isFake"] is True and len(data["comparison"]) == 5
    row = data["review"]["rows"][0]
    saved = client.post("/api/review", json={"rows": [{"id": row["id"], "real_game": "yes", "gameplay_accurate": "no", "notes": "n"}]}).get_json()
    assert saved["tally"]["inaccurate"] == 1 and saved["tally"]["checked"] == 1
    assert client.get("/api/inspect").get_json()["review"]["rows"][0]["notes"] == "n"

    keys = [t["key"] for t in data["titles"][:2]]
    merged = client.post("/api/titles/merge", json={"keys": keys, "target": "Merged Game"}).get_json()
    assert merged["titles"][0]["key"] == "merged game"
    undone = client.post("/api/titles/undo", json={"key": keys[0]}).get_json()
    assert keys[0] in [t["key"] for t in undone["titles"]]

    export = client.post("/api/export").get_json()
    assert "summary.json" in export["files"]
    assert json.loads((pathlib.Path(export["folder"]) / "summary.json").read_text(encoding="utf-8"))["review"]["inaccurate"] == 1

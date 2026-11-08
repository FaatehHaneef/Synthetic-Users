"""Runs the interface headlessly on a fake run. No network, no keys."""
import pathlib
import shutil
import sys

import pytest
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from synthusers.generate import FakeProvider, RUNS_DIR, run_generation

RUN = "pytest-fake"


@pytest.fixture
def run(monkeypatch):
    monkeypatch.chdir(ROOT)
    path = RUNS_DIR / f"{RUN}.jsonl"
    path.unlink(missing_ok=True)
    run_generation(FakeProvider(), path, 24, ["default", "persona"], 8)
    yield
    path.unlink(missing_ok=True)
    shutil.rmtree(ROOT / "results" / RUN, ignore_errors=True)


def app():
    test = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    test.session_state["run_name"] = RUN
    return test.run()


def text_of(test):
    return " ".join(item.value for item in list(test.markdown) + list(test.caption))


def test_every_screen_renders_with_labels(run):
    test = app()
    assert not test.exception
    page = text_of(test)
    assert "SIMULATED PARTICIPANTS" in page and "does not reproduce it" in page
    assert "FAKE DEMO DATA" in page
    assert "Authors' proposed use" in page
    assert "reviewed responses had inaccurate gameplay" in page
    assert "Chart description" in page


def test_export_writes_files(run):
    test = app()
    next(b for b in test.button if b.label == "Export results").click().run()
    assert not test.exception
    written = {p.name for p in (ROOT / "results" / RUN).iterdir()}
    assert {"summary.json", "titles_counts.csv", "review_sample.csv", "top1_share.png", "distinct_per_100.png", "persona_titles.csv"} <= written

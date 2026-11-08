"""API keys: loading from .env and falling back when a project's daily quota runs out."""
import datetime as dt
import json
import os
import pathlib
import re

try:
    from zoneinfo import ZoneInfo

    PACIFIC = ZoneInfo("America/Los_Angeles")
except Exception:  # no timezone database on this machine
    PACIFIC = dt.timezone(dt.timedelta(hours=-8))


class AllKeysExhausted(Exception):
    """Every key is out of quota for today (or invalid)."""


def pacific_date():
    """Gemini daily quotas reset at midnight Pacific."""
    return dt.datetime.now(PACIFIC).date().isoformat()


def load_keys(env_path=".env", environ=None):
    """Return keys in order: GEMINI_KEY_1, GEMINI_KEY_2, ... then GEMINI_API_KEY. Any count works."""
    values = dict(os.environ if environ is None else environ)
    path = pathlib.Path(env_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                values[name.strip()] = value.strip().strip("'\"")
    numbered = []
    for name, value in values.items():
        match = re.fullmatch(r"GEMINI_KEY_(\d+)", name)
        if match and value:
            numbered.append((int(match.group(1)), value))
    keys = [value for _, value in sorted(numbered)]
    single = values.get("GEMINI_API_KEY")
    if single:
        keys.append(single)
    return list(dict.fromkeys(keys))


class KeyPool:
    """Hands out the first key with quota left. Logs refer to keys by number only, never by value."""

    def __init__(self, keys, model, state_path=None, today=pacific_date):
        if not keys:
            raise AllKeysExhausted("No keys found. Put GEMINI_KEY_1=... in .env")
        self.keys = list(keys)
        self.model = model
        self.state_path = pathlib.Path(state_path) if state_path else None
        self.today = today
        self.invalid = set()  # this session only
        self.state = self._load()

    def _load(self):
        if self.state_path and self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"date": self.today(), "models": {}}

    def _save(self):
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _model_state(self):
        if self.state.get("date") != self.today():
            self.state = {"date": self.today(), "models": {}}
            self._save()
        return self.state["models"].setdefault(self.model, {"used": {}, "exhausted": []})

    def current(self):
        """Return (key_number, key). Key numbers start at 1."""
        state = self._model_state()
        for number, key in enumerate(self.keys, 1):
            if number not in state["exhausted"] and number not in self.invalid:
                return number, key
        if self.invalid:
            raise AllKeysExhausted(
                f"{len(self.invalid)} key(s) were rejected by Google this session and the rest have no quota left. "
                "See Google's message above. Waiting for the daily reset will not fix a rejected key."
            )
        raise AllKeysExhausted(
            "All keys are out of quota. Daily quotas reset at midnight Pacific "
            "(1 pm Pakistan time in winter). The run is saved, start it again to continue."
        )

    def record_use(self, number):
        used = self._model_state()["used"]
        used[str(number)] = used.get(str(number), 0) + 1
        self._save()

    def mark_exhausted(self, number):
        exhausted = self._model_state()["exhausted"]
        if number not in exhausted:
            exhausted.append(number)
        self._save()

    def mark_invalid(self, number):
        self.invalid.add(number)

    def status(self):
        """Per-key status for display. Contains no key values."""
        state = self._model_state()
        rows = []
        for number in range(1, len(self.keys) + 1):
            if number in self.invalid:
                label = "invalid"
            elif number in state["exhausted"]:
                label = "out of quota today"
            else:
                label = "available"
            rows.append({"key": number, "requests_today": state["used"].get(str(number), 0), "status": label})
        return rows

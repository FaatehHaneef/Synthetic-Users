"""Generate synthetic interviews. Candidates share a prompt but are not part of each other's input."""
import collections
import dataclasses
import datetime as dt
import json
import pathlib
import random
import re
import time
import uuid

import requests

from .keys import AllKeysExhausted, KeyPool, load_keys
from .prompts import PERSONAS, SYSTEM_INSTRUCTION, build_prompt

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.6-flash"
KEY_STATE_PATH = pathlib.Path("data/key_state.json")
QUOTA_LOG_PATH = pathlib.Path("data/quota_log.jsonl")
RUNS_DIR = pathlib.Path("data/runs")
MAX_SERVER_RETRIES = 5
MAX_MINUTE_STRIKES = 4
MAX_EMPTY_REQUESTS = 5


class ApiError(Exception):
    """A problem that retrying or switching keys will not fix."""

    def __init__(self, message, kind="other"):
        super().__init__(message)
        self.kind = kind  # 'busy', 'offline' or 'other'


@dataclasses.dataclass
class Candidate:
    text: str
    finish_reason: str = "STOP"


@dataclasses.dataclass
class Result:
    candidates: list
    key_number: int = 0
    usage: dict = dataclasses.field(default_factory=dict)


# ----- providers ------------------------------------------------------------


class FakeProvider:
    """Offline stand-in for building and rehearsing. Every answer is marked as fake."""

    name = "fake"
    GAMES = ["Journey"] * 8 + ["Flower"] * 3 + ["Bioshock"] * 2 + [
        "Shadow of the Colossus", "The Last of Us", "journey.", "Dear Esther", "Firewatch", "Hollow Knight",
        "NieR: Automata", "Breath of the Wild", "The Legend of Zelda: Breath of the Wild",
    ]
    LINES = [
        "the story stayed with me for weeks and the ending made me cry",
        "the music swelled as the world opened up in front of my character",
        "every painted landscape looked like a canvas I could walk through",
        "my own choices shaped what happened and I felt responsible for them",
        "the quiet atmosphere of the ruins made me feel small and calm",
    ]

    def __init__(self, seed=7, model="fake-model"):
        self.model = model
        self.random = random.Random(seed)

    def generate(self, prompt, system, n):
        candidates = []
        for _ in range(n):
            lines = self.random.sample(self.LINES, 3)
            answer = "[FAKE DEMO TEXT, not from any model] When I played it, " + ", and ".join(lines) + "."
            if self.random.random() < 0.04:
                answer = "It was nice."
            title = self.random.choice(self.GAMES)
            candidates.append(Candidate(f"{answer}\nResearcher: What is the title of the game?\nParticipant: {title}"))
        return Result(candidates=candidates, key_number=0)


class GeminiProvider:
    """Calls Gemini. Daily quota out: next key. Per-minute limit: wait on the same key."""

    name = "gemini"

    def __init__(self, keys, model=DEFAULT_MODEL, rpm=5, max_tokens=8192, thinking_level=None,
                 state_path=KEY_STATE_PATH, session=None, sleep=time.sleep, clock=time.monotonic,
                 on_event=None, pool=None, log_path=None, retry_budget=None):
        self.log_path = pathlib.Path(log_path) if log_path else None
        self.retry_budget = retry_budget  # seconds per call, None means retry by count
        self.model = model
        self.pool = pool or KeyPool(keys, model, state_path)
        self.min_interval = 60.0 / rpm + 0.5
        self.max_tokens = max_tokens
        self.thinking_level = thinking_level
        self.session = session or requests.Session()
        self.sleep = sleep
        self.clock = clock
        self.on_event = on_event or (lambda message: None)
        self.last_call = {}
        self.minute_strikes = collections.Counter()

    def _body(self, prompt, system, n):
        config = {"candidateCount": n, "maxOutputTokens": self.max_tokens}
        if self.thinking_level:
            config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }

    def _pace(self, number):
        if number in self.last_call:
            wait = self.min_interval - (self.clock() - self.last_call[number])
            if wait > 0:
                self.sleep(wait)
        self.last_call[number] = self.clock()

    def _scrub(self, text):
        for key in self.pool.keys:
            text = text.replace(key, "[KEY]")
        return text

    def _log(self, number, status, **details):
        """One line per API response. Key number only, and error text has keys removed."""
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "model": self.model,
                 "key_number": number, "status": status, **details}
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _elapsed(self, start):
        return self.clock() - start

    def _out_of_retries(self, start, failures):
        if self.retry_budget is None:
            return failures > MAX_SERVER_RETRIES
        return self._elapsed(start) >= self.retry_budget

    def _request_timeout(self, start):
        return 180 if self.retry_budget is None else max(5, self.retry_budget - self._elapsed(start))

    def generate(self, prompt, system, n):
        server_failures = 0
        start = None
        while True:
            number, key = self.pool.current()
            self._pace(number)
            if start is None:
                start = self.clock()
            try:
                response = self.session.post(
                    API_URL.format(model=self.model),
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=self._body(prompt, system, n),
                    timeout=self._request_timeout(start),
                )
            except requests.RequestException as error:
                server_failures += 1
                if self._out_of_retries(start, server_failures):
                    kind = "offline" if isinstance(error, requests.ConnectionError) else "busy"
                    raise ApiError(self._scrub(f"Network problem: {type(error).__name__}"), kind=kind) from None
                self._backoff(server_failures, f"network problem ({type(error).__name__})", start)
                continue

            status = response.status_code
            if status == 200:
                self.pool.record_use(number)
                self.minute_strikes[number] = 0
                data = response.json()
                self._log(number, status, usage=data.get("usageMetadata", {}))
                return self._parse(data, number)
            payload = self._json(response)
            message = self._scrub(str(payload.get("error", {}).get("message", response.text[:400])))
            self._log(number, status, error=self._scrub(json.dumps(payload, ensure_ascii=False)))

            if status == 429:
                kind, delay = classify_429(payload)
                if kind == "daily":
                    self.pool.mark_exhausted(number)
                    self.on_event(f"Key {number} is out of daily quota, moving to the next key.")
                    continue
                if kind == "unknown":
                    raise ApiError(f"Gemini sent a limit error this code does not recognise, stopping: {message}")
                self.minute_strikes[number] += 1
                if self.minute_strikes[number] >= MAX_MINUTE_STRIKES:
                    self.pool.mark_invalid(number)
                    self.on_event(f"Key {number} keeps getting rate limited, skipping it for this session.")
                    continue
                wait = max(delay or 0, self.min_interval)
                if self.retry_budget is not None and self._elapsed(start) + wait > self.retry_budget:
                    raise ApiError(f"Per-minute limit wait is longer than the retry budget: {message}", kind="busy")
                self.on_event(f"Key {number} hit the per-minute limit, waiting {wait:.0f} s.")
                self.sleep(wait)
                continue
            if status in (401, 403) or "API_KEY_INVALID" in json.dumps(payload) or "API key not valid" in message:
                self.pool.mark_invalid(number)
                self.on_event(f"Key {number} was rejected ({status}): {message}")
                continue
            if status >= 500:
                server_failures += 1
                if self._out_of_retries(start, server_failures):
                    raise ApiError(f"Gemini server error {status}: {message}", kind="busy")
                self._backoff(server_failures, f"server error {status}", start)
                continue
            raise ApiError(f"Gemini returned {status}: {message}")

    def _backoff(self, attempt, reason, start):
        wait = min(5 * 2 ** (attempt - 1), 60)
        if self.retry_budget is not None:
            wait = min(wait, max(0.5, self.retry_budget - self._elapsed(start)))
        self.on_event(f"Temporary problem: {reason}, retrying in {wait:g} s.")
        self.sleep(wait)

    @staticmethod
    def _json(response):
        try:
            return response.json()
        except ValueError:
            return {}

    @staticmethod
    def _parse(payload, number):
        candidates = []
        for item in payload.get("candidates", []):
            parts = item.get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
            candidates.append(Candidate(text, item.get("finishReason", "UNKNOWN")))
        return Result(candidates=candidates, key_number=number, usage=payload.get("usageMetadata", {}))


def classify_429(payload):
    """Return ('daily', 'minute' or 'unknown', retry delay in seconds or None)."""
    error = payload.get("error", {})
    delay = None
    names = [str(error.get("message", ""))]
    for detail in error.get("details", []):
        if "retryDelay" in detail:
            match = re.match(r"([\d.]+)s", str(detail["retryDelay"]))
            delay = float(match.group(1)) if match else None
        names.extend(str(violation.get("quotaId", "")) for violation in detail.get("violations", []))
    text = " ".join(names)
    if re.search(r"per[ _-]?day", text, re.I):
        return "daily", delay
    if re.search(r"per[ _-]?minute", text, re.I):
        return "minute", delay
    return "unknown", delay


# ----- parsing and the paper's quality heuristics (section 3.2) --------------


def parse_reply(text):
    """Split a reply into (answer, title). Answer: text before 'Researcher:', first paragraph only."""
    text = text.replace("**", "").strip()
    text = re.sub(r"^\s*Participant\s*:\s*", "", text)
    match = re.search(r"Researcher\s*:", text)
    head, tail = (text[: match.start()], text[match.start():]) if match else (text, "")
    paragraphs = head.strip().split("\n")
    answer = paragraphs[0].strip() if paragraphs else ""
    title_match = re.search(r"Participant\s*:\s*(.*)", tail)
    title = title_match.group(1).strip() if title_match else ""
    return answer, title


def quality_status(answer, title):
    """Return 'valid' or the reason for discarding the reply."""
    if len(answer.split()) < 10:
        return "too_short"
    if re.search(r"(.{11,200})\1", answer, re.S):
        return "repetition"
    if not title:
        return "no_title"
    return "valid"


# ----- planning ---------------------------------------------------------------


@dataclasses.dataclass
class Job:
    condition: str
    persona_id: object
    n: int


def persona_targets(n):
    """Spread n participants evenly across the personas."""
    base, extra = divmod(n, len(PERSONAS))
    return [base + (1 if index < extra else 0) for index in range(len(PERSONAS))]


def plan_next_job(done, n, conditions, candidates):
    """Pick the next request. Keeps groups balanced in case quota stops the run midway."""
    totals = {c: sum(v for (cond, _), v in done.items() if cond == c) for c in conditions}
    for condition in sorted((c for c in conditions if totals[c] < n), key=lambda c: (totals[c], conditions.index(c))):
        if condition == "default":
            return Job("default", None, min(candidates, n - done.get(("default", None), 0)))
        remaining = [t - done.get(("persona", i), 0) for i, t in enumerate(persona_targets(n))]
        persona_id = max(range(len(remaining)), key=lambda i: (remaining[i], -i))
        return Job("persona", persona_id, min(candidates, remaining[persona_id]))
    return None


def estimate_requests(n, conditions, candidates):
    total = 0
    if "default" in conditions:
        total += -(-n // candidates)
    if "persona" in conditions:
        total += sum(-(-t // candidates) for t in persona_targets(n))
    return total


# ----- running ----------------------------------------------------------------


def read_records(path):
    path = pathlib.Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_generation(provider, path, n, conditions, candidates, max_requests=None, on_progress=None, on_event=None):
    """Generate until each group has n valid interviews. Safe to stop and start again."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_records(path)
    for record in existing:
        if (record["provider"], record["model"]) != (provider.name, provider.model):
            raise ApiError(f"{path.name} holds data from {record['provider']}/{record['model']}. Use a new run name.")

    done = collections.Counter()
    for record in existing:
        if record["status"] == "valid":
            done[(record["condition"], record["persona_id"])] += 1
    if max_requests is None:
        max_requests = int(estimate_requests(n, conditions, candidates) * 1.5) + 5

    target = n * len(conditions)
    requests_made = empty_streak = 0
    discards = collections.Counter()
    stopped = "complete"
    say = on_event or (lambda message: None)
    with path.open("a", encoding="utf-8") as handle:
        while True:
            job = plan_next_job(done, n, conditions, candidates)
            if job is None:
                break
            if requests_made >= max_requests:
                stopped = "request_cap"
                break
            persona = None if job.persona_id is None else PERSONAS[job.persona_id]
            try:
                result = provider.generate(build_prompt(persona), SYSTEM_INSTRUCTION, job.n)
            except AllKeysExhausted as error:
                say(str(error))
                stopped = "all_keys_exhausted"
                break
            except ApiError as error:
                say(str(error))
                stopped = "api_error"
                break
            requests_made += 1
            request_id = uuid.uuid4().hex[:12]
            valid_now = 0
            for index, candidate in enumerate(result.candidates):
                answer, title = parse_reply(candidate.text)
                status = quality_status(answer, title) if candidate.text.strip() else f"empty:{candidate.finish_reason}"
                record = {
                    "id": f"{request_id}-{index}", "request_id": request_id, "provider": provider.name,
                    "model": provider.model, "condition": job.condition, "persona_id": job.persona_id,
                    "persona": persona, "candidate_index": index, "candidates_requested": job.n,
                    "key_number": result.key_number, "finish_reason": candidate.finish_reason, "status": status,
                    "answer": answer, "title_raw": title, "words": len(answer.split()), "raw": candidate.text,
                    "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                if status == "valid":
                    done[(job.condition, job.persona_id)] += 1
                    valid_now += 1
                else:
                    discards[status] += 1
            handle.flush()
            empty_streak = 0 if valid_now else empty_streak + 1
            if on_progress:
                on_progress(min(sum(done.values()), target), target, requests_made)
            if empty_streak >= MAX_EMPTY_REQUESTS:
                say("Several requests in a row produced nothing usable, stopping. Check the raw replies.")
                stopped = "no_valid_replies"
                break
    return {"stopped": stopped, "requests": requests_made, "valid": sum(done.values()), "target": target,
            "discards": dict(discards)}


def probe_candidates(provider, candidates):
    """One real request, to see whether candidateCount works and gives different answers."""
    result = provider.generate(build_prompt(), SYSTEM_INSTRUCTION, candidates)
    parsed = [parse_reply(c.text) for c in result.candidates]
    return {
        "requested": candidates,
        "returned": len(result.candidates),
        "distinct_answers": len({answer for answer, _ in parsed}),
        "titles": [title for _, title in parsed],
        "words": [len(answer.split()) for answer, _ in parsed],
        "finish_reasons": [c.finish_reason for c in result.candidates],
        "statuses": [quality_status(answer, title) for answer, title in parsed],
        "key_number": result.key_number,
        "usage": result.usage,
    }


def make_provider(name, model, rpm=5, max_tokens=8192, thinking_level=None, on_event=None, max_keys=None):
    if name == "fake":
        return FakeProvider()
    if name == "gemini":
        return GeminiProvider(load_keys()[:max_keys], model, rpm=rpm, max_tokens=max_tokens,
                              thinking_level=thinking_level, on_event=on_event, log_path=QUOTA_LOG_PATH)
    raise ValueError(f"Unknown provider: {name}")

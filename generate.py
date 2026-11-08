"""Command line for generating interviews. See README.md."""
import argparse
import json
import sys

from synthusers.generate import (ApiError, DEFAULT_MODEL, GeminiProvider, RUNS_DIR, make_provider, probe_candidates, run_generation)
from synthusers.keys import AllKeysExhausted, KeyPool, load_keys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="generate interviews (safe to stop and restart)")
    run.add_argument("--provider", choices=["fake", "gemini"], default="fake")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--name", required=True, help="run name, saved as data/runs/NAME.jsonl")
    run.add_argument("--n", type=int, default=178, help="participants per group")
    run.add_argument("--candidates", type=int, default=1, help="answers per request (Gemini 3.6 Flash only allows 1)")
    run.add_argument("--conditions", nargs="+", choices=["default", "persona"], default=["default", "persona"])
    run.add_argument("--rpm", type=float, default=5, help="requests per minute allowed per key")
    run.add_argument("--max-tokens", type=int, default=8192)
    run.add_argument("--thinking-level", default=None)
    run.add_argument("--max-requests", type=int, default=None)
    run.add_argument("--max-keys", type=int, default=None, help="use only the first N keys")

    probe = commands.add_parser("probe", help="one real request to test candidateCount")
    probe.add_argument("--model", default=DEFAULT_MODEL)
    probe.add_argument("--candidates", type=int, default=1)
    probe.add_argument("--max-tokens", type=int, default=8192)
    probe.add_argument("--thinking-level", default=None)

    keys = commands.add_parser("keys", help="show how many keys are loaded and their status today")
    keys.add_argument("--model", default=DEFAULT_MODEL)

    args = parser.parse_args()
    if args.command == "keys":
        print(json.dumps(KeyPool(load_keys(), args.model, "data/key_state.json").status(), indent=2))
    elif args.command == "probe":
        provider = GeminiProvider(load_keys(), args.model, max_tokens=args.max_tokens,
                                  thinking_level=args.thinking_level, on_event=print)
        try:
            print(json.dumps(probe_candidates(provider, args.candidates), indent=2, ensure_ascii=False))
        except (ApiError, AllKeysExhausted) as error:
            print(error)
            return 1
    else:
        provider = make_provider(args.provider, args.model, args.rpm, args.max_tokens, args.thinking_level, on_event=print, max_keys=args.max_keys)
        summary = run_generation(
            provider, RUNS_DIR / f"{args.name}.jsonl", args.n, args.conditions, args.candidates, args.max_requests,
            on_progress=lambda done, target, count: print(f"{done}/{target} interviews, {count} requests", flush=True),
            on_event=print,
        )
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())

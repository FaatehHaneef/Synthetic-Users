"""Command line for analysing a saved run: python analyze.py data/runs/NAME.jsonl"""
import argparse
import json

from synthusers.analyze import write_outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="path to a run's JSONL file")
    args = parser.parse_args()
    directory = write_outputs(args.run)
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    print(f"Wrote {directory}")
    for condition, group in summary["groups"].items():
        print(f"{condition}: top game {group['top_game']} {group['top1_share']:.1f}%, "
              f"{group['distinct']} different games in {group['mentions']} mentions")


if __name__ == "__main__":
    main()

"""python -m planner 2027-01 [2027-02 ...]   or   python -m planner 2027   (whole year)
python -m planner --check-facts               check that every fact in the facts files fits
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .build import ROOT, build_month, check_facts
from .dates import MONTHS
from .facts import load_facts


def parse_months(args: list[str]) -> list[tuple[int, int]]:
    months = []
    for a in args:
        if "-" in a:
            y, m = a.split("-")
            months.append((int(y), int(m)))
        else:
            months += [(int(a), m) for m in range(1, 13)]
    return months


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="planner", description="Generate monthly planner PDFs.")
    ap.add_argument("months", nargs="*", help="YYYY-MM, or YYYY for the whole year")
    ap.add_argument("--check-facts", action="store_true",
                    help="check every fact (all days, all rows) without building pages")
    ap.add_argument("--config", type=Path, default=ROOT / "planner.toml")
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    args = ap.parse_args(argv)

    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    facts = load_facts([ROOT / p for p in config.get("facts", [])])
    habits = config.get("habits", [])

    if args.check_facts:
        labelled = {f"{f.day:02d} {MONTHS[f.month - 1][:3]} #{i}: {f.title[:40]}": f
                    for key in sorted(facts) for i, f in enumerate(facts[key], start=1)}
        (ROOT / "build").mkdir(exist_ok=True)
        issues = check_facts(labelled, ROOT / "build")
        print(f"{len(labelled)} facts checked, {len(issues)} problem(s)")
        for i in issues:
            print(f"  OVERFLOW {i}")
    if not args.months and not args.check_facts:
        ap.error("give at least one month, or --check-facts")
    for year, month in parse_months(args.months):
        report = build_month(year, month, facts, habits, ROOT / "build", args.out)
        print(report.text())
    if args.months:
        print(f"PDFs in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

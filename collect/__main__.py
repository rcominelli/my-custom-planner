"""Collect facts of the day into the facts Excel file.

  python -m collect candidates 11              gather raw candidates for November
  python -m collect candidates 11 --days 1-5   only some days
  python -m collect picture "Compaq Portable"  free picture of a Wikipedia article
  python -m collect check drafts.json          check that written facts fit the page
  python -m collect merge drafts.json          add written facts to the Excel file
  python -m collect pictures                   download free pictures named in 'Picture From'
  python -m collect missing                    list the facts without a picture (CSV)
  python -m collect credits                    fetch picture credits again, cleaned up

The step in between (choosing candidates and writing each fact in original words, sized
to the page) is done by Claude, from the candidates file. Pictures and credits are
fetched by the separate 'pictures' step.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from pathlib import Path

from planner.render import ensure_writable

from . import factsfile, pictures
from .sources import SOURCES, THEMES, collect_day

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS = ROOT / "data" / "facts" / "tech-history.xlsx"
CANDIDATES = ROOT / "build" / "candidates"


def _days(month: int, spec: str | None) -> list[int]:
    last = calendar.monthrange(2028, month)[1]
    if not spec:
        return list(range(1, last + 1))
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def cmd_candidates(args) -> int:
    existing = {r["URL"] for r in factsfile.read(args.facts) if r.get("URL")}
    month, errors = args.month, []
    stem = CANDIDATES / f"{args.theme}-{month:02d}"
    sources, days = args.sources.split(","), _days(month, args.days)
    # keep earlier results for other days or sources, so sources can be collected separately
    out = []
    if stem.with_suffix(".json").exists():
        prev = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
        source_names = {"tdith": "This Day in Tech History", "chm": "Computer History Museum",
                        "wikipedia": "Wikipedia", "inbox": "inbox"}
        redo = {source_names[s] for s in sources}
        out = [d for d in prev if not (d["day"] in days and d["source"] in redo)]
    for day in days:
        found, errs = collect_day(month, day, args.theme, sources)
        errors += errs
        for c in found:
            d = c.to_dict()
            d["in_file"] = c.url in existing
            out.append(d)
        print(f"{month:02d}-{day:02d}: {len(found)} candidate(s)"
              f"{' (' + str(len(errs)) + ' source error(s))' if errs else ''}")
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    out.sort(key=lambda d: (d["day"], d["source"] == "Wikipedia"))
    stem.with_suffix(".json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    md = []
    for d in out:
        md.append(f"## {d['month']:02d}-{d['day']:02d} | {d['source']} | {d['kind']} | {d['year']}"
                  f"{' | ALREADY IN FILE' if d['in_file'] else ''}\n**{d['title']}**\n{d['url']}\n"
                  f"wikipedia: {', '.join(d['wikipedia'])}\n\n{d['text'][:1500]}\n")
    stem.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    for e in errors:
        print("  ERROR", e)
    print(f"{len(out)} candidates -> {stem.with_suffix('.md').relative_to(ROOT)}")
    return 0


def cmd_picture(args) -> int:
    pic = pictures.find(args.article)
    print(json.dumps(pic, indent=1) if pic else "No free picture found")
    if pic:
        print(pictures.credit(pic))
    return 0


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].rstrip("-")


def _attach(row: dict, pic: dict, args) -> bool:
    stem = f"{row['Month']:02d}-{row['Day']:02d}-{_slug(row['Title'] or '')}"
    try:
        path = pictures.download(pic, args.facts.parent / "images", stem)
    except Exception as e:
        print(f"  {stem}: picture download failed ({e})")
        return False
    row["Image"], row["Image Credit"] = f"images/{path.name}", pictures.credit(pic)
    return True


def cmd_merge(args) -> int:
    """Add (or update) facts from a JSON list. No network: pictures are a separate step."""
    ensure_writable(args.facts)
    rows = factsfile.read(args.facts)
    for r in rows:
        if (r.get("Title") or r.get("Text")) and not r.get("Status"):
            r["Status"] = "approved"
    by_key = {(r["Month"], r["Day"], (r.get("Title") or "").strip().lower()): r for r in rows}
    drafts = json.loads(Path(args.drafts).read_text(encoding="utf-8"))
    added = updated = skipped = 0
    for f in drafts:
        key = (f["month"], f["day"], f["title"].strip().lower())
        row = by_key.get(key)
        if f.get("update"):
            # change an existing row: any of text / new_title / picture
            if row is None:
                print(f"  {f['month']:02d}-{f['day']:02d} update: no fact titled {f['title']!r}")
                continue
            if f.get("text"):
                row["Text"], row["Status"] = f["text"], f.get("status", "draft")
            if f.get("new_title"):
                row["Title"], row["Status"] = f["new_title"], f.get("status", "draft")
            if f.get("picture") and not row.get("Image"):
                row["Picture From"] = f["picture"]
            updated += 1
            continue
        if row is not None:
            skipped += 1
            continue
        row = {"Month": f["month"], "Day": f["day"], "Year": f.get("year"), "Title": f["title"],
               "Text": f["text"], "Source": f.get("source"), "URL": f.get("url"),
               "Picture From": f.get("picture"), "Status": f.get("status", "draft")}
        rows.append(row)
        by_key[key] = row
        added += 1
    factsfile.write(args.facts, rows)
    print(f"{args.facts.relative_to(ROOT)}: {added} fact(s) added, {updated} updated, "
          f"{skipped} already present")
    print("Next: python -m collect pictures")
    return 0


def cmd_pictures(args) -> int:
    """Download free pictures for rows with 'Picture From' and no Image yet."""
    ensure_writable(args.facts)
    rows = factsfile.read(args.facts)
    todo = [r for r in rows if r.get("Picture From") and not r.get("Image")
            and (args.month is None or r["Month"] == args.month)]
    if not todo:
        print("No pictures to fetch.")
        return 0
    print(f"Looking up {len(todo)} picture(s) on Wikipedia...")
    found = pictures.find_many(sorted({r["Picture From"] for r in todo}))
    got = 0
    for r in todo:
        pic = found.get(r["Picture From"])
        if not pic:
            print(f"  {r['Month']:02d}-{r['Day']:02d} no free picture for {r['Picture From']!r}")
        elif _attach(r, pic, args):
            got += 1
        factsfile.write(args.facts, rows)  # save progress after each picture
    print(f"{got} of {len(todo)} picture(s) downloaded")
    return 0


def cmd_credits(args) -> int:
    """Fetch author and license again for downloaded pictures and rewrite their credit.

    Only credits made by this tool (ending in 'Wikimedia Commons') are rewritten; credits
    typed by hand are left alone.
    """
    ensure_writable(args.facts)
    rows = factsfile.read(args.facts)
    todo = [r for r in rows if r.get("Image") and r.get("Picture From")
            and str(r.get("Image Credit") or "").endswith("Wikimedia Commons")
            and (args.month is None or r["Month"] == args.month)]
    if not todo:
        print("No credits to refresh.")
        return 0
    print(f"Fetching credits for {len(todo)} picture(s) from Wikipedia...")
    found = pictures.find_many(sorted({r["Picture From"] for r in todo}))
    changed = 0
    for r in todo:
        pic = found.get(r["Picture From"])
        if not pic:
            print(f"  {r['Month']:02d}-{r['Day']:02d} no longer found: {r['Picture From']!r} (credit kept)")
            continue
        new = pictures.credit(pic)
        if new != r["Image Credit"]:
            r["Image Credit"] = new
            changed += 1
    factsfile.write(args.facts, rows)
    print(f"{changed} of {len(todo)} credit(s) updated")
    return 0


def cmd_missing(args) -> int:
    """Export the facts that have no picture to a CSV file (opens in Excel)."""
    import csv
    rows = [r for r in factsfile.read(args.facts) if (r.get("Title") or r.get("Text"))
            and not r.get("Image") and (r.get("Status") or "") != "rejected"
            and (args.month is None or r["Month"] == args.month)]
    for r in rows:
        r["Reason"] = ("no free picture found for 'Picture From'" if r.get("Picture From")
                       else "no 'Picture From' given")
    out = Path(args.out) if args.out else ROOT / "output" / "missing-pictures.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    ensure_writable(out)
    cols = ["Month", "Day", "Year", "Title", "Source", "URL", "Picture From", "Status", "Reason"]
    # utf-8-sig and semicolons: Excel on Windows (with European settings) opens it directly
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c) or "" for c in cols])
    tried = sum(1 for r in rows if r.get("Picture From"))
    print(f"{len(rows)} fact(s) without a picture: {tried} with no free picture found, "
          f"{len(rows) - tried} without 'Picture From'")
    print(f"List written to {out}")
    return 0


def cmd_check(args) -> int:
    """Check that drafted facts fit the page, before merging them."""
    from planner.build import check_facts
    from planner.facts import Fact
    drafts = json.loads(Path(args.drafts).read_text(encoding="utf-8"))
    facts = {}
    for i, f in enumerate(drafts):
        if f.get("update") and not f.get("text"):
            continue
        fact = Fact(f["month"], f["day"], f.get("year"), f.get("new_title") or f["title"], f.get("text", ""),
                    f.get("source", ""), f.get("url", ""))
        facts[f"{f['month']:02d}-{f['day']:02d} #{i}: {fact.title[:40]}"] = fact
    out = ROOT / "build" / "check"
    out.mkdir(parents=True, exist_ok=True)
    issues = check_facts(facts, out)
    print(f"{len(facts)} drafted facts checked, {len(issues)} problem(s)")
    for i in issues:
        print(f"  OVERFLOW {i}")
    return 1 if issues else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="collect", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--facts", type=Path, default=DEFAULT_FACTS, help="facts Excel file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates", help="gather raw candidates for a month")
    c.add_argument("month", type=int)
    c.add_argument("--days", help="e.g. 4 or 1-10")
    c.add_argument("--theme", default="tech", choices=sorted(THEMES))
    c.add_argument("--sources", default=",".join(SOURCES), help="comma-separated: " + ",".join(SOURCES))
    p = sub.add_parser("picture", help="find the free picture of a Wikipedia article")
    p.add_argument("article")
    m = sub.add_parser("merge", help="add written facts (JSON) to the facts file")
    m.add_argument("drafts")
    k = sub.add_parser("check", help="check that drafted facts (JSON) fit the page")
    k.add_argument("drafts")
    cr = sub.add_parser("credits", help="fetch picture credits again and rewrite them (cleaned)")
    cr.add_argument("--month", type=int)
    x = sub.add_parser("missing", help="export the facts without a picture to a CSV file")
    x.add_argument("--month", type=int)
    x.add_argument("--out", help="CSV file (default: output/missing-pictures.csv)")
    g = sub.add_parser("pictures", help="download free pictures for rows with 'Picture From'")
    g.add_argument("--month", type=int)
    args = ap.parse_args(argv)
    return {"candidates": cmd_candidates, "picture": cmd_picture, "merge": cmd_merge,
            "pictures": cmd_pictures, "check": cmd_check,
            "missing": cmd_missing, "credits": cmd_credits}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

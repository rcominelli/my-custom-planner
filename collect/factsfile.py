"""Read and write the facts Excel file (the format the planner reads)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

COLUMNS = ["Month", "Day", "Year", "Title", "Text", "Source", "URL",
           "Picture From", "Image", "Image Credit", "Status"]
WIDTHS = [8, 6, 7, 45, 90, 26, 60, 30, 40, 40, 10]
HOW_TO = [
    "One row per fact. Month and Day say which calendar day the fact belongs to (any year).",
    "Year is the year the event happened; it is shown under the title.",
    "Rows without Title and Text are ignored (they are placeholders for days without facts).",
    "Several facts for the same day: add rows with the same Month and Day.",
    "The planner picks one per day and rotates through all of them over the years before repeating one.",
    "Source is the name shown in the credit line, URL the page where the fact can be checked.",
    "Picture From (optional): a Wikipedia article (or File:name). 'python -m collect pictures' downloads",
    "its main picture if it is freely licensed, and fills in Image and Image Credit.",
    "Image (optional): picture file, relative to this file's folder (e.g. images/12-29-shockley.png).",
    "Image Credit: author and license of the picture, printed next to it.",
    "Status: approved, draft (written automatically, not reviewed yet) or rejected (never printed).",
    "Empty Status counts as approved. The planner's report lists the draft facts it printed.",
]


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    ws = openpyxl.load_workbook(path).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows)]
    out = []
    for r in rows:
        row = {c: (r[header.index(c)] if c in header and header.index(c) < len(r) else None) for c in COLUMNS}
        if row["Month"] is None or row["Day"] is None:
            continue
        row["Month"], row["Day"] = int(row["Month"]), int(row["Day"])
        out.append(row)
    return out


def write(path: Path, rows: list[dict]) -> None:
    """Facts sorted by day (original order kept within a day); empty days keep one placeholder row."""
    facts = [r for r in rows if r.get("Title") or r.get("Text")]
    order = {id(r): i for i, r in enumerate(facts)}
    by_day: dict[tuple[int, int], list[dict]] = {}
    for r in facts:
        by_day.setdefault((r["Month"], r["Day"]), []).append(r)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Facts"
    ws.append(COLUMNS)
    day = dt.date(2028, 1, 1)  # leap year: 29 February included
    while day.year == 2028:
        key = (day.month, day.day)
        for r in sorted(by_day.get(key, []), key=lambda r: order[id(r)]):
            ws.append([r.get(c) for c in COLUMNS])
        if key not in by_day:
            ws.append([day.month, day.day] + [None] * (len(COLUMNS) - 2))
        day += dt.timedelta(days=1)

    for i, width in enumerate(WIDTHS):
        ws.column_dimensions[chr(65 + i)].width = width
    ws.freeze_panes = "A2"
    table = Table(displayName="Facts", ref=f"A1:{chr(64 + len(COLUMNS))}{ws.max_row}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(table)

    notes = wb.create_sheet("How to use")
    for line in HOW_TO:
        notes.append([line])
    notes["A1"].font = Font(bold=True)
    notes.column_dimensions["A"].width = 110
    wb.save(path)

"""One-off: convert the 2026 working Excel into the year-independent facts format.

Input : reference/2026-data/Planner RaF - Computer Tech Facts - Days Year.xlsx
Output: data/facts/tech-history.xlsx
Pictures already prepared in data/facts/images/ named MM-DD-*.png are linked in the Image column.

The output has one row per calendar day (366, including 29 February) so it is easy to
complete; extra facts for the same day are added as extra rows.

Usage:  python tools/convert_facts.py
"""
from pathlib import Path
import datetime as dt
from urllib.parse import urlparse

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reference/2026-data/Planner RaF - Computer Tech Facts - Days Year.xlsx"
OUT = ROOT / "data/facts/tech-history.xlsx"
IMAGES = OUT.parent / "images"
SOURCE_NAMES = {
    "www.computerhistory.org": "Computer History Museum",
    "thisdayintechhistory.com": "This Day in Tech History",
    "www.history.com": "History.com",
}

COLUMNS = ["Month", "Day", "Year", "Title", "Text", "Source", "URL", "Image"]
WIDTHS = [8, 6, 7, 45, 90, 26, 60, 40]


def main():
    ws_in = openpyxl.load_workbook(SRC).worksheets[0]
    facts = {}
    for row in ws_in.iter_rows(min_row=2, values_only=True):
        date, title, year, text, url = row[0], row[6], row[7], row[8], row[9]
        if title:
            facts[(date.month, date.day)] = (year, title.strip(), " ".join(str(text).split()), url)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Facts"
    ws.append(COLUMNS)
    day = dt.date(2028, 1, 1)  # a leap year, so 29 February gets a row
    while day.year == 2028:
        f = facts.get((day.month, day.day))
        if f:
            year, title, text, url = f
            source = SOURCE_NAMES[urlparse(url).netloc]
            image = next(IMAGES.glob(f"{day:%m-%d}-*"), None)
            ws.append([day.month, day.day, year, title, text, source, url,
                       f"images/{image.name}" if image else None])
        else:
            ws.append([day.month, day.day] + [None] * 6)
        day += dt.timedelta(days=1)

    for i, width in enumerate(WIDTHS):
        ws.column_dimensions[chr(65 + i)].width = width
    for cell in ws["E"][1:]:
        cell.alignment = Alignment(wrap_text=False, vertical="top")
    ws.freeze_panes = "A2"
    table = Table(displayName="Facts", ref=f"A1:H{ws.max_row}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(table)

    notes = wb.create_sheet("How to use")
    for line in [
        "One row per fact. Month and Day say which calendar day the fact belongs to (any year).",
        "Year is the year the event happened; it is shown under the title.",
        "Leave Title and Text empty if you have no fact for that day yet: the row is ignored.",
        "Several facts for the same day: add extra rows with the same Month and Day.",
        "The planner then picks one per day, rotating by planner year, so facts change year over year.",
        "Source is the name shown in the credit line, URL the link to the original page.",
        "Image (optional): picture file, relative to this Excel file's folder (e.g. images/12-29-shockley.png).",
        "The picture is scaled to fit the 'Picture area' of the notes page, in the bottom-right corner.",
    ]:
        notes.append([line])
    notes["A1"].font = Font(bold=True)
    notes.column_dimensions["A"].width = 110

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"{OUT.relative_to(ROOT)}: {len(facts)} facts, {ws.max_row - 1} rows")


if __name__ == "__main__":
    main()

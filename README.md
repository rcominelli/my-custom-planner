# My Custom Planner

Generator for a printable A5 day-on-two-pages planner, starting with 2027.
One PDF per month is built from SVG page templates (designed in Inkscape) and Excel files
with a fact for each day.

## Usage

Step-by-step setup and daily commands for Windows: **[docs/GUIDE.md](docs/GUIDE.md)**.

Requirements: Python 3.11+, Inkscape 1.2+ (on `PATH`, or set the `INKSCAPE` environment
variable to its full path), and `pip install -r requirements.txt`.

```bash
python -m planner 2027-01            # one month
python -m planner 2027-01 2027-02    # several months
python -m planner 2027               # whole year
```

Output for each month, in `output/YYYY-MM/`:

| File | Use |
|------|-----|
| `planner-YYYY-MM-A5.pdf` | All pages in reading order, for checking on screen |
| `planner-YYYY-MM-A4-print.pdf` | Print-ready: 4 A5 pages per A4 sheet in booklet order. Print double-sided, **flip on short edge**, page sizing **Fit**, then cut each sheet in half. |
| `report.txt` | Days without a fact, facts that don't fit, font problems |

## How a month is built

A month with D days has 2D + 2 A5 pages:

| Page | Side | Template | Content |
|------|------|----------|---------|
| 1 | right | `01-month-cover.svg` | Month cover |
| 2k | left | `02-day-tasks.svg` | Day k: date, mini calendars (this and next month), task list with pre-filled habits, daily tracker, appointments |
| 2k+1 | right | `03-day-notes.svg` | Day k: date, fact of the day with source, day count, daily notes, picture of the fact |
| last | left | `04-month-end.svg` | Notes and tasks to be migrated to the next month |

The page count must be a multiple of 4 for booklet printing. When it isn't (months of 28
and 30 days), two extra "Notes" pages go before the month-end page.

## Checks

- **Facts that don't fit:** each fact is laid out in an unlimited frame and compared with
  the real one. Inkscape silently drops lines that don't fit, so any overflow is reported
  and must be fixed by shortening the text in Excel. Font sizes are never reduced. The
  report also flags titles wider than the fact frame and source lines wider than the
  notes area.
- **Fonts:** if Inkscape falls back to a substitute font, the report lists it.

## Editing

- **Layout:** open a file in `templates/` with Inkscape and save it as Inkscape SVG. The
  generator finds fields by their Inkscape label (Object > Layers and Objects). Keep the
  labels the generator uses: `Day Number`, `Month Year Weekday`, `Month Name`,
  `Notes Title`, `Day Count`, `Fact - Title`, `Fact - Date`, `Fact - Text`,
  `Fact - Text frame`, `Fact - Source`, `Picture area`, `Habit - Priority`, `Habit - Text`, the groups
  `Calendar - This Month` and `Calendar - Next Month` (with cells `MN`, `WKr0`, `Drc`),
  `Fact` and `Daily Notes Lines`.
- **Habits:** `planner.toml`, one `[[habits]]` block per row.
- **Facts:** `data/facts/*.xlsx`, one row per fact with columns Month, Day, Year, Title,
  Text, Source, URL, Image, Image Credit, Status. Rows without Title and Text, and rows
  with Status `rejected`, are ignored. With several facts for the same day, the one used
  rotates by year. Several files can be listed in
  `planner.toml`.
- **Pictures:** the Image column holds a file path relative to the Excel file's folder
  (e.g. `images/12-29-shockley.png`). The picture is scaled to fit the hidden
  `Picture area` rectangle on the notes page, keeping its proportions, and pinned to its
  bottom-right corner (at most half the page wide and 90 mm high). Resize the rectangle
  in Inkscape to change the rule.

## Collecting facts

`collect/` builds the facts file; it is separate from the planner, which only reads the
Excel file.

```bash
python -m collect candidates 11      # raw candidates for November -> build/candidates/
python -m collect merge drafts.json  # add written facts, download free pictures + credits
python -m planner --check-facts      # check every fact fits its frame
```

1. **Candidates** come from This Day in Tech History, the Computer History Museum,
   Wikipedia's "On this day" feed (events, births and deaths filtered by theme) and text
   files saved by hand in `data/facts/inbox/` (fallback for sites that block automated
   access). Their text is the sources' own wording and is only used as reference, so
   `build/` is never committed.
2. **Writing** is done by Claude in a session: it picks 3-4 facts per day, writes each
   one in its own words sized to the frame, credits the page it is based on, and names a
   Wikipedia article for the picture. The result is a JSON list (see `merge` in
   `collect/__main__.py`).
3. **Merge** adds the facts with Status `draft`. Pictures come from Wikimedia Commons,
   only with free licenses, with author and license in Image Credit. Entries with
   `"update": true` change an existing fact (text, title, picture) instead.
4. **Review** in Excel: set Status to `approved` or `rejected` (see docs/GUIDE.md, 3.2).

The planner picks one fact per day, cycling through all of a day's facts over the years
in a fixed shuffled order, so the same file serves many years.

## Repository layout

```
planner/       the generator (python -m planner)
collect/       the facts collector (python -m collect)
templates/     one Inkscape SVG per page type
data/facts/    facts per calendar day (Excel), their pictures (images/) and hand-saved texts (inbox/)
docs/          hands-on guide
fonts/         free fonts used by the templates, with licenses
planner.toml   configuration: fact files, habits
tools/         one-off scripts that created templates/ and data/ from reference/
reference/     2025-2026 source material, kept as-is
```

## Decisions

- **Rendering:** the templates use Inkscape flowed text, and only Inkscape recalculates
  wrapping and alignment after the text changes. The generator fills the SVGs with Python
  and exports them through the Inkscape command line.
- **Week numbers:** ISO 8601. All date values are calculated, not read from Excel.
- **Fonts:** free and redistributable (see `fonts/README.md`), so the repo can become
  public. On Linux they are loaded from `fonts/` automatically. On Windows and macOS,
  install them first.
- **Facts:** each fact shows its source name and URL, for credit and so it can be checked.
  Titles must not be wider than the fact text.
- **Pictures:** facts and pictures from third-party sites are copyrighted. That's fine
  while the repo is private. Before publishing, start a fresh public repo without
  `data/facts/` and its history.

## Roadmap

1. **Personal 2027 planner (current).** Same layout as 2026 with facts restored, one file
   per month.
2. **Facts.** Complete the 2027 facts. Optionally add freely licensed sources (for example
   Wikipedia, CC BY-SA) and publish an empty facts template for other people.
3. **Configurable planner (to be analysed separately).** Page sizes, week start, date
   formats, choosing and placing widgets, possibly an online tool. This needs a layout
   defined in code rather than hand-drawn SVGs, and a layout of its own that doesn't
   derive from Franklin Planner.

# My Custom Planner

Generator for a printable A5 day-on-two-pages planner, starting with 2027.
One PDF per month is built from SVG page templates (designed in Inkscape) and an
Excel file with a computer-tech fact for each day.

## Status

Setup and analysis only. No generator code yet.

## Repository layout

```
reference/                 Source material, kept as-is (not used by the generator)
  2025-templates/          Nov-Dec 2025 single-page templates (with the tech-fact block)
  2026-october/            Full October 2026 month: 4-page Inkscape template + exported PDFs
  2026-mini-calendars/     Month modules that were pasted into pages by hand in 2026
data/                      Tech facts per day (Excel; incomplete, test months only)
```

To be added: `templates/` (one SVG per page type), `src/` (the generator), `fonts/`,
and `output/` (generated PDFs, not committed).

## Month structure

A month with D days has 2D + 2 A5 pages:

| Page | Side | Content |
|------|------|---------|
| 1 | right | Month cover (later: month overview table) |
| 2k | left | Day k: date, mini calendars (this and next month), prioritized task list, daily tracker, appointment schedule |
| 2k+1 | right | Day k: date, tech fact of the day (to be reintroduced), daily notes |
| 2D+2 | left | End of month: notes and tasks to be migrated to the next month |

Printing: pages are grouped in fours and printed as a booklet on A4. Each sheet is
folded and cut, which gives two A5 leaves printed front and back.

## Decisions so far

- **Rendering:** the templates use Inkscape flowed text (`shape-inside`). Only Inkscape
  recalculates wrapping and alignment after the text changes, so the generator fills
  the SVGs with Python and exports them with the Inkscape command line.
- **Overflow:** if a fact doesn't fit its frame, the generator flags it and the text is
  shortened in Excel. Font sizes are never reduced.
- **Week numbers:** ISO 8601, as in the 2026 mini calendars.
- **Fonts:** the plan is to move to freely redistributable fonts so the repo can become
  public: TeX Gyre Schola (in place of Century Schoolbook), TeX Gyre Adventor (Century
  Gothic) and Carlito (Calibri). A replacement for Brush Script MT is still open.

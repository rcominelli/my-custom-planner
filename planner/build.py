"""Assemble one month: fill the page templates, export, merge, lay out for printing, report."""
from __future__ import annotations

import copy
import datetime as dt
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import dates, render
from .facts import Fact, pick
from PIL import Image

from .svgfill import Page, clone_with_offset, place_image, row_pitch, set_cell, set_text

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
COVER, TASKS, NOTES, MONTH_END = (TEMPLATES / n for n in (
    "01-month-cover.svg", "02-day-tasks.svg", "03-day-notes.svg", "04-month-end.svg"))


@dataclass
class Report:
    month: str
    pages: int = 0
    sheets: int = 0
    missing_facts: list[dt.date] = field(default_factory=list)
    pictures: int = 0
    picture_problems: list[str] = field(default_factory=list)
    overflows: list[str] = field(default_factory=list)
    font_warnings: set[str] = field(default_factory=set)

    def text(self) -> str:
        out = [f"{self.month}: {self.pages} A5 pages, {self.sheets} A4 sheets, {self.pictures} picture(s)"]
        if self.missing_facts:
            out.append(f"  No fact for {len(self.missing_facts)} day(s): "
                       + ", ".join(d.strftime("%d") for d in self.missing_facts))
        out += [f"  PICTURE {p}" for p in self.picture_problems]
        out += [f"  OVERFLOW {o}" for o in self.overflows]
        if self.font_warnings:
            out.append(f"  WARNING substitute fonts embedded: {sorted(self.font_warnings)} "
                       "(install the fonts in fonts/)")
        if not (self.missing_facts or self.overflows or self.font_warnings or self.picture_problems):
            out.append("  All checks passed")
        return "\n".join(out)


# --- pages -----------------------------------------------------------------

def cover_page(year, month):
    p = Page(COVER)
    p.set("Month Name", f"{dates.MONTHS[month - 1]}\n{year}")
    return p


def fill_calendar(p: Page, group_label: str, year: int, month: int):
    g = p.find(group_label)
    p.set("MN", dates.month_name(year, month), g)
    for r, (week, days) in enumerate(dates.month_grid(year, month), start=1):
        set_cell(p.find(f"WK{r}0", g), str(week), dim=False)
        for c, d in enumerate(days, start=1):
            set_cell(p.find(f"D{r}{c}", g), str(d.day), dim=d.month != month)


def tasks_page(day: dt.date, habits: list[dict]):
    p = Page(TASKS)
    p.set("Day Number", str(day.day))
    p.set("Month Year Weekday", f"{dates.MONTHS[day.month - 1]}\n{day.year}\n{dates.WEEKDAYS[day.weekday()]}")
    fill_calendar(p, "Calendar - This Month", day.year, day.month)
    fill_calendar(p, "Calendar - Next Month", *dates.next_month(day.year, day.month))

    prio, text = p.find("Habit - Priority"), p.find("Habit - Text")
    pitch = row_pitch(text)
    for i, habit in enumerate(habits):
        if habit.get("priority"):
            set_text(clone_with_offset(prio, i * pitch), habit["priority"])
        set_text(clone_with_offset(text, i * pitch), habit.get("text", ""))
    for proto in (prio, text):
        proto.getparent().remove(proto)
    return p


def notes_page(day: dt.date | None, fact: Fact | None, title: str = "Daily Notes", report=None):
    p = Page(NOTES)
    area = p.find("Picture area")
    if fact and fact.image:
        try:
            with Image.open(fact.image) as im:
                size, mime = im.size, Image.MIME.get(im.format, "image/png")
            place_image(area, fact.image, size, mime)
            report.pictures += 1
        except (OSError, ValueError) as e:
            report.picture_problems.append(f"{day:%d %b}: cannot use {fact.image.name} ({e.__class__.__name__})")
    p.set("Notes Title", title)
    if day:
        p.set("Day Number", str(day.day))
        p.set("Month Year Weekday", f"{dates.MONTHS[day.month - 1]}\n{day.year}\n{dates.WEEKDAYS[day.weekday()]}")
        p.set("Day Count", dates.day_count(day))
    else:
        for label in ("Day Number", "Month Year Weekday", "Day Count"):
            p.set(label, "")
    p.set("Fact - Title", fact.title if fact else "")
    p.set("Fact - Date", fact.date_line if fact else "")
    p.set("Fact - Text", fact.text if fact else "")
    p.set("Fact - Source", fact.source_line if fact else "")
    return p


def month_end_page(year, month, title=None):
    p = Page(MONTH_END)
    p.set("Month Name", dates.month_name(year, month))
    ny, nm = dates.next_month(year, month)
    p.set("Notes Title", title or f"Notes & Tasks – To be migrated to {dates.month_name(ny, nm)}")
    return p


# --- overflow check --------------------------------------------------------

def _style_px(style: str, prop: str, default: float) -> float:
    m = re.search(rf"{prop}:([0-9.]+)", style or "")
    return float(m.group(1)) if m else default


def check_facts(facts_by_day: dict[dt.date, Fact], build_dir: Path) -> list[str]:
    """Lay every fact out once in an unlimited frame and compare with the real frame.

    Flags: text taller than its frame (Inkscape would silently drop the extra lines),
    a title wider than the frame, a source line wider than the notes area.
    """
    if not facts_by_day:
        return []
    p = Page(NOTES)
    group, frame = p.find("Fact"), p.find("Fact - Text frame")
    text, title, source = p.find("Fact - Text"), p.find("Fact - Title"), p.find("Fact - Source")
    lines_id = p.find("Daily Notes Lines").get("id")

    probe = copy.deepcopy(frame)
    probe.set("id", "probe-frame")
    probe.set("style", "fill:#ff0000")
    group.append(probe)
    ids = {}
    for n, (day, fact) in enumerate(facts_by_day.items()):
        tall = copy.deepcopy(frame)
        tall.set("id", f"m-frame-{n}")
        tall.set("height", "5000")
        group.append(tall)
        for kind, el, value in (("text", text, fact.text), ("title", title, fact.title),
                                ("source", source, fact.source_line)):
            c = copy.deepcopy(el)
            for e in c.iter():
                if e.get("id"):
                    e.set("id", f"{e.get('id')}-m{n}")
            if kind == "text":
                c.set("style", c.get("style").replace(f"url(#{frame.get('id')})", f"url(#m-frame-{n})"))
            group.append(c)
            set_text(c, value)
            ids[(day, kind)] = c.get("id")
    svg = build_dir / "measure-facts.svg"
    p.write(svg)
    box = render.query_all(svg, build_dir)

    fx, fy, fw, fh = box["probe-frame"]
    lx, _, lw, _ = box[lines_id]
    line_pitch = _style_px(text.get("style"), "font-size", 8) * _style_px(text.get("style"), "line-height", 1.15)
    issues = []
    for day in facts_by_day:
        tx, ty, tw, th = box[ids[(day, "text")]]
        over = (ty + th) - (fy + fh)
        if over > 1.0:
            issues.append(f"{day:%d %b}: fact text needs about {math.ceil(over / line_pitch)} "
                          f"more line(s) than the frame holds; shorten it")
        x, _, w, _ = box[ids[(day, "title")]]
        if x + w > fx + fw + 0.5:
            issues.append(f"{day:%d %b}: title is {x + w - fx - fw:.0f}px wider than the fact frame")
        x, _, w, _ = box[ids[(day, "source")]]
        if x + w > lx + lw + 0.5:
            issues.append(f"{day:%d %b}: source line is {x + w - lx - lw:.0f}px wider than the notes area")
    return issues


# --- month -----------------------------------------------------------------

def build_month(year: int, month: int, facts, habits, build_root: Path, out_root: Path) -> Report:
    tag = f"{year}-{month:02d}"
    build_dir, out_dir = build_root / tag, out_root / tag
    build_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = Report(tag)

    days = dates.days_of_month(year, month)
    chosen = {d: pick(facts, d) for d in days}
    report.missing_facts = [d for d, f in chosen.items() if f is None]

    pages = [("cover", cover_page(year, month))]
    for d in days:
        pages.append((f"{d.day:02d}-tasks", tasks_page(d, habits)))
        pages.append((f"{d.day:02d}-notes", notes_page(d, chosen[d], report=report)))
    if (len(pages) + 1) % 4:  # booklet groups of 4: add a blank notes spread before the month end
        pages.append(("extra-left", month_end_page(year, month, title="Notes")))
        pages.append(("extra-right", notes_page(None, None, title="Notes")))
    pages.append(("month-end", month_end_page(year, month)))

    svgs = []
    for i, (name, page) in enumerate(pages, start=1):
        path = build_dir / f"{i:03d}-{name}.svg"
        page.write(path)
        svgs.append(path)
    pdfs = render.export_pdfs(svgs, build_dir)

    a5 = out_dir / f"planner-{tag}-A5.pdf"
    render.merge(pdfs, a5)
    report.pages = len(pdfs)
    report.sheets = render.impose_booklets(a5, out_dir / f"planner-{tag}-A4-print.pdf")
    report.font_warnings = render.unexpected_fonts(a5)
    report.overflows = check_facts({d: f for d, f in chosen.items() if f}, build_dir)
    (out_dir / "report.txt").write_text(report.text() + "\n", encoding="utf-8")
    return report

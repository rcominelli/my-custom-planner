"""Facts of the day, read from one or more Excel files (see data/facts/*.xlsx)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from .dates import MONTHS

REQUIRED = ["Month", "Day", "Title", "Text"]
OPTIONAL = ["Year", "Source", "URL", "Image"]


@dataclass(frozen=True)
class Fact:
    month: int
    day: int
    year: int | None
    title: str
    text: str
    source: str
    url: str
    image: Path | None = None  # resolved path; may not exist (reported at build time)

    @property
    def date_line(self) -> str:
        base = f"{MONTHS[self.month - 1]} {self.day}"
        return f"{base}, {self.year}" if self.year else base

    @property
    def source_line(self) -> str:
        if self.source and self.url:
            return f"Source: {self.source}, {self.url}"
        return f"Source: {self.source or self.url}" if (self.source or self.url) else ""


def _clean(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _resolve_image(base: Path, name: str) -> Path:
    """Relative to the Excel file's folder; a bare file name is also looked up in images/."""
    path = base / name
    if not path.exists() and (base / "images" / name).exists():
        path = base / "images" / name
    return path.resolve()


def load_facts(paths: list[Path]) -> dict[tuple[int, int], list[Fact]]:
    facts: dict[tuple[int, int], list[Fact]] = {}
    for path in paths:
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header = [_clean(h).lower() for h in next(rows)]
        missing = [c for c in REQUIRED if c.lower() not in header]
        if missing:
            raise ValueError(f"{path}: missing column(s) {missing}; expected {REQUIRED + OPTIONAL}")
        col = {name: header.index(name.lower()) for name in REQUIRED + OPTIONAL if name.lower() in header}

        def get(row, name):
            return row[col[name]] if name in col and col[name] < len(row) else None

        for row in rows:
            title, text = _clean(get(row, "Title")), _clean(get(row, "Text"))
            if not title and not text:
                continue
            year, image = get(row, "Year"), _clean(get(row, "Image"))
            fact = Fact(int(get(row, "Month")), int(get(row, "Day")),
                        int(year) if year not in (None, "") else None,
                        title, text, _clean(get(row, "Source")), _clean(get(row, "URL")),
                        _resolve_image(path.parent, image) if image else None)
            facts.setdefault((fact.month, fact.day), []).append(fact)
    return facts


def pick(facts: dict[tuple[int, int], list[Fact]], day: dt.date) -> Fact | None:
    """One fact per day; with several candidates, rotate by year so they change year over year."""
    candidates = facts.get((day.month, day.day))
    return candidates[day.year % len(candidates)] if candidates else None

"""Calendar values shown on the pages. Week numbers are ISO 8601 (weeks start on Monday)."""
from __future__ import annotations

import calendar
import datetime as dt

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def month_name(year: int, month: int) -> str:
    return f"{MONTHS[month - 1]} {year}"


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def days_of_month(year: int, month: int) -> list[dt.date]:
    return [dt.date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)]


def day_count(day: dt.date) -> str:
    """e.g. '346th Day, 20 Left, Week 50'."""
    doy = day.timetuple().tm_yday
    left = (dt.date(day.year, 12, 31) - day).days
    return f"{ordinal(doy)} Day, {left} Left, Week {day.isocalendar().week}"


def month_grid(year: int, month: int) -> list[tuple[int, list[dt.date]]]:
    """Six weeks starting on the Monday on or before the 1st: [(iso_week, [7 dates]), ...]."""
    first = dt.date(year, month, 1)
    start = first - dt.timedelta(days=first.weekday())
    rows = []
    for r in range(6):
        week = [start + dt.timedelta(days=7 * r + c) for c in range(7)]
        rows.append((week[0].isocalendar().week, week))
    return rows

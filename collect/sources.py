"""Candidate facts for one calendar day, from several sources.

A candidate is raw material, not a finished fact: the text is the source's own wording
and is only used as a reference to write an original summary.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lxml import html

from planner.dates import MONTHS
from .http import get, get_json

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "facts" / "inbox"

# Words that make a Wikipedia event or person relevant for a theme.
THEMES = {
    "tech": r"comput|software|hardware|internet|world wide web|programm|electronic|semiconductor|"
            r"transistor|microprocessor|integrated circuit|calculat|telegra|telephon|radio|televis|"
            r"satellite|robot|video game|cryptograph|algorithm|mathematician|engineer|inventor|"
            r"physicist|information theor|artificial intelligence|microsoft|apple inc|\bibm\b|intel\b|"
            r"google|unix|linux|network|digital|cybern|patent",
}


# People whose description matches these are skipped unless a STRONG term also matches
# (e.g. "television host" is skipped, "actress and inventor" is kept).
NOT_PEOPLE = re.compile(r"actor|actress|singer|television|radio (host|personality|presenter)|presenter|"
                        r"personality|comedian|footballer|wrestler|model|politician|journalist|"
                        r"broadcaster|producer|director|player|racer|chef", re.I)
STRONG = re.compile(r"comput|software|programm|inventor|invented|cryptograph|internet|video ?game|"
                    r"electronic|engineer", re.I)


@dataclass
class Candidate:
    month: int
    day: int
    source: str
    kind: str  # event, birth, death, note
    year: int | None
    title: str
    text: str
    url: str
    wikipedia: list[str] = field(default_factory=list)  # related article titles

    def to_dict(self):
        return asdict(self)


def _text(el) -> str:
    return " ".join(el.text_content().split())


def _year(s: str) -> int | None:
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s)
    return int(m.group(1)) if m else None


def tdith(month: int, day: int) -> list[Candidate]:
    """thisdayintechhistory.com: day archive, then each post."""
    base = f"https://thisdayintechhistory.com/{month:02d}/{day:02d}/"
    doc = html.fromstring(get(base))
    links = []
    for a in doc.xpath('//h2//a[@href]'):
        href = a.get("href").split("#")[0]
        if href.startswith(base) and href != base and href not in links:
            links.append(href)
    out = []
    for url in links:
        post = html.fromstring(get(url))
        title = _text(post.xpath('//h1')[0]) if post.xpath('//h1') else url
        paras = [_text(p) for p in post.xpath('//div[contains(@class,"fl-post-content")]//p')]
        paras = [p for p in paras if p]
        year = _year(paras[0]) if paras else None
        body = " ".join(paras[1:] if paras and len(paras[0]) < 40 else paras)
        out.append(Candidate(month, day, "This Day in Tech History", "event", year, title, body, url))
    return out


def chm(month: int, day: int) -> list[Candidate]:
    """Computer History Museum, This Day in History."""
    url = f"https://www.computerhistory.org/tdih/{MONTHS[month - 1].lower()}/{day}/"
    doc = html.fromstring(get(url))
    out = []
    for t in doc.xpath('//*[contains(@class,"tdih-entry-title")]'):
        box = t.getparent()
        while box is not None and not box.xpath('.//*[contains(@class,"tdih-entry-content")]'):
            box = box.getparent()
        if box is None:
            continue
        date = box.xpath('.//*[contains(@class,"tdih-entry-date")]')
        body = box.xpath('.//*[contains(@class,"tdih-entry-content")]')
        anchor = next((a.get("id") for a in [box, *box.iterancestors()] if a.get("id")), "")
        out.append(Candidate(month, day, "Computer History Museum", "event",
                             _year(_text(date[0])) if date else None, _text(t),
                             _text(body[0]) if body else "", f"{url}#{anchor}" if anchor else url))
    return out


def wikipedia(month: int, day: int, theme: str) -> list[Candidate]:
    """Wikipedia 'On this day' feed: events, births and deaths matching the theme."""
    feed = get_json(f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{month:02d}/{day:02d}")
    pattern = re.compile(THEMES[theme], re.I)
    out, seen = [], set()
    for kind, key in (("event", "selected"), ("event", "events"), ("birth", "births"), ("death", "deaths")):
        for e in feed.get(key, []):
            pages = e.get("pages", [])
            main = pages[0] if pages else {}
            haystack = e["text"] + " " + " ".join(p.get("description", "") for p in pages[:2])
            if kind != "event":  # people: judge by their own description only
                haystack = e["text"] + " " + main.get("description", "")
            if not pattern.search(haystack) or e["text"] in seen:
                continue
            if kind != "event" and NOT_PEOPLE.search(e["text"]) and not STRONG.search(e["text"]):
                continue
            seen.add(e["text"])
            url = main.get("content_urls", {}).get("desktop", {}).get("page", "")
            out.append(Candidate(month, day, "Wikipedia", kind, e.get("year"), e["text"],
                                 main.get("extract", ""), url,
                                 [p["title"] for p in pages[:3]]))
    return out


def inbox(month: int, day: int) -> list[Candidate]:
    """Text files saved by hand in data/facts/inbox/, named MM-DD-anything.txt (or .md)."""
    out = []
    for f in sorted(INBOX.glob(f"{month:02d}-{day:02d}*")):
        if f.suffix.lower() in (".txt", ".md"):
            text = " ".join(f.read_text(encoding="utf-8", errors="replace").split())
            out.append(Candidate(month, day, "inbox", "note", _year(text), f.name, text, ""))
    return out


SOURCES = {"tdith": tdith, "chm": chm, "wikipedia": wikipedia, "inbox": inbox}


def collect_day(month: int, day: int, theme: str, sources: list[str]) -> tuple[list[Candidate], list[str]]:
    candidates, errors = [], []
    for name in sources:
        try:
            fn = SOURCES[name]
            candidates += fn(month, day, theme) if name == "wikipedia" else fn(month, day)
        except Exception as e:  # one failing site must not stop the others
            errors.append(f"{month:02d}-{day:02d} {name}: {e.__class__.__name__}: {e}")
    return candidates, errors

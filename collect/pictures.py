"""Freely licensed pictures from Wikimedia Commons, found through Wikipedia articles.

Lookups are batched (up to 50 titles per request) because Wikimedia rate-limits
unauthenticated clients.
"""
from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from .http import get, get_json

API = "https://en.wikipedia.org/w/api.php"
WIDTH = 1000  # px; about 340 dpi at the maximum printed width of 74 mm
BATCH = 50


def _plain(s: str) -> str:
    s = " ".join(unescape(re.sub(r"<[^>]+>", " ", s or "")).split())
    s = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", s))
    if s.count("(") != s.count(")"):  # drop a dangling "(..." left by stripped markup
        s = s.split("(")[0].strip()
    return s


def _chunks(items):
    items = list(items)
    for i in range(0, len(items), BATCH):
        yield items[i:i + BATCH]


def _page_images(articles: list[str]) -> dict[str, str]:
    """article title -> file name of its main picture."""
    out = {}
    for chunk in _chunks(articles):
        q = get_json(API, {"action": "query", "format": "json", "formatversion": 2, "redirects": 1,
                           "prop": "pageimages", "piprop": "name", "titles": "|".join(chunk)})
        alias = {}
        for kind in ("normalized", "redirects"):
            for n in q["query"].get(kind, []):
                alias[n["to"]] = alias.get(n["from"], n["from"])
        for page in q["query"]["pages"]:
            if page.get("pageimage"):
                out[alias.get(page["title"], page["title"])] = page["pageimage"]
    return out


def _file_info(files: list[str]) -> dict[str, dict]:
    """file name -> picture dict, for free files on Commons only."""
    out = {}
    for chunk in _chunks(files):
        q = get_json(API, {"action": "query", "format": "json", "formatversion": 2,
                           "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": WIDTH,
                           "titles": "|".join(f"File:{f}" for f in chunk)})
        alias = {n["to"]: n["from"] for n in q["query"].get("normalized", [])}
        for page in q["query"]["pages"]:
            # Files stored on Wikipedia itself (not Commons) are usually non-free "fair use".
            if page.get("imagerepository") != "shared" or not page.get("imageinfo"):
                continue
            info = page["imageinfo"][0]
            meta = info.get("extmetadata", {})
            if str(meta.get("NonFree", {}).get("value", "")).lower() in ("true", "1"):
                continue
            artist = _plain(meta.get("Artist", {}).get("value", "")) or "Unknown author"
            if len(artist) > 50:
                artist = artist[:47].rstrip() + "..."
            name = alias.get(page["title"], page["title"]).removeprefix("File:")
            out[name.replace(" ", "_")] = {
                "file": name, "url": info.get("thumburl") or info["url"], "original": info["url"],
                "page": info["descriptionurl"], "artist": artist,
                "license": _plain(meta.get("LicenseShortName", {}).get("value", ""))}
    return out


def find_many(refs: list[str]) -> dict[str, dict | None]:
    """Each ref is a Wikipedia article title or 'File:...'. Returns ref -> picture or None."""
    articles = [r for r in refs if not r.startswith("File:")]
    page_files = _page_images(articles) if articles else {}
    file_of = {r: (r[5:] if r.startswith("File:") else page_files.get(r)) for r in refs}
    infos = _file_info([f for f in set(file_of.values()) if f])
    return {r: (infos.get(f.replace(" ", "_")) if f else None) for r, f in file_of.items()}


def find(ref: str) -> dict | None:
    return find_many([ref])[ref]


def credit(pic: dict) -> str:
    lic = pic["license"]
    lic = "public domain" if lic.lower() in ("public domain", "pd") else lic
    return f"Picture: {pic['artist']}, {lic}, Wikimedia Commons"


MAX_PX = 1200  # longest side kept when shrinking an original


def download(pic: dict, folder: Path, stem: str) -> Path:
    """Resized version if reachable, else the original shrunk locally. Raises if both fail."""
    folder.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in dict.fromkeys([pic["url"], pic.get("original") or pic["url"]]):
        ext = Path(urlparse(url).path).suffix.lower() or ".jpg"
        if ext == ".svg":  # originals of drawings are SVG, which the planner can't place
            continue
        try:
            data = get(url, binary=True)
        except Exception as e:
            errors.append(f"{urlparse(url).netloc}: {e}")
            continue
        path = folder / f"{stem}{ext}"
        path.write_bytes(data)
        with Image.open(path) as im:
            if max(im.size) > MAX_PX:
                im.thumbnail((MAX_PX, MAX_PX))
                im.save(path)
        return path
    raise OSError("; ".join(errors) or "only an SVG original is available")

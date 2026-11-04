"""Polite HTTP: identifies itself, waits between requests, retries on rate limits, caches."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "build" / "cache"
USER_AGENT = "my-custom-planner/0.1 (+https://github.com/rcominelli/my-custom-planner)"
DELAY = 2.0  # seconds between requests to the same host

_last: dict[str, float] = {}


def get(url: str, params: dict | None = None, binary: bool = False, cache: bool = True):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    key = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if cache and key.exists():
        data = key.read_bytes()
        return data if binary else data.decode("utf-8", errors="replace")

    host = urllib.parse.urlparse(url).netloc
    for attempt in range(5):
        wait = _last.get(host, 0) + DELAY - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 4:
                # rate limited: wait as long as the server asks (Wikimedia sends Retry-After)
                retry = e.headers.get("Retry-After", "")
                time.sleep(min(int(retry) + 1, 120) if retry.isdigit() else 2 ** (attempt + 3))
                continue
            raise
    if cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        key.write_bytes(data)
    return data if binary else data.decode("utf-8", errors="replace")


def get_json(url: str, params: dict | None = None):
    return json.loads(get(url, params))

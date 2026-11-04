"""Inkscape calls (export, measurement) and PDF assembly."""
from __future__ import annotations

import csv
import io
import os
import platform
import shutil
import subprocess
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "fonts"
EXPECTED_FONTS = ("TeXGyreSchola", "TeXGyreAdventor", "Carlito", "Caveat")
A4_LANDSCAPE = (841.8898, 595.2756)


WINDOWS_DEFAULT = Path(r"C:\Program Files\Inkscape\bin\inkscape.com")


def inkscape_exe() -> str:
    """INKSCAPE env var, else PATH, else the default Windows install folder.

    On Windows the console variant inkscape.com is needed: inkscape.exe does not read
    commands from stdin or print query results.
    """
    exe = (os.environ.get("INKSCAPE") or shutil.which("inkscape.com") or shutil.which("inkscape")
           or (str(WINDOWS_DEFAULT) if WINDOWS_DEFAULT.exists() else None))
    if not exe:
        raise RuntimeError("Inkscape not found: install Inkscape 1.2+ or set the INKSCAPE environment variable")
    return exe


def _env(build_dir: Path) -> dict:
    """On Linux, make Inkscape see fonts/ without installing them system-wide."""
    env = dict(os.environ)
    if platform.system() == "Linux":
        conf = build_dir / "fonts.conf"
        conf.write_text(
            '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>\n'
            '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
            f"  <dir>{FONTS}</dir>\n  <cachedir>{build_dir / 'fontcache'}</cachedir>\n</fontconfig>\n",
            encoding="utf-8")
        env["FONTCONFIG_FILE"] = str(conf)
    return env


def export_pdfs(svgs: list[Path], build_dir: Path) -> list[Path]:
    """Export each SVG to a PDF next to it, in one Inkscape process when possible.

    The SVGs must be in build_dir. Inkscape runs inside build_dir with bare file names,
    so paths with drive letters or spaces never reach its command syntax.
    """
    exe, env = inkscape_exe(), _env(build_dir)
    pdfs = [s.with_suffix(".pdf") for s in svgs]
    for p in pdfs:
        p.unlink(missing_ok=True)
    script = "".join(f"file-open:{s.name}; export-filename:{p.name}; export-do; file-close\n"
                     for s, p in zip(svgs, pdfs)) + "quit\n"
    subprocess.run([exe, "--shell"], input=script, text=True, env=env, cwd=build_dir,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for s, p in zip(svgs, pdfs):  # fallback: one process per file
        if not p.exists():
            subprocess.run([exe, str(s), "--export-type=pdf", f"--export-filename={p}"],
                           env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pdfs


def query_all(svg: Path, build_dir: Path) -> dict[str, tuple[float, float, float, float]]:
    """Visual bounding boxes (x, y, w, h) of every element, in document units."""
    out = subprocess.run([inkscape_exe(), "--query-all", str(svg)], env=_env(build_dir),
                         check=True, capture_output=True, text=True).stdout
    return {r[0]: tuple(float(v) for v in r[1:5]) for r in csv.reader(io.StringIO(out)) if len(r) == 5}


def merge(pdfs: list[Path], out: Path) -> None:
    writer = PdfWriter()
    for p in pdfs:
        writer.append(str(p))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        writer.write(f)


def impose_booklets(a5_pdf: Path, out: Path) -> int:
    """Groups of 4 A5 pages on one A4 sheet: front [4|1], back [2|3].

    Print double-sided, flip on short edge, actual size. Fold or cut each sheet in half:
    the right half carries pages 1/2, the left half pages 3/4.
    """
    pages = PdfReader(str(a5_pdf)).pages
    W, H = A4_LANDSCAPE
    writer = PdfWriter()

    def place(sheet, page, half):
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        tx = half * W / 2 + (W / 2 - w) / 2 - float(box.left)
        ty = (H - h) / 2 - float(box.bottom)
        sheet.merge_transformed_page(page, Transformation().translate(tx, ty))

    sheets = 0
    for i in range(0, len(pages), 4):
        group = list(pages[i:i + 4]) + [None] * (4 - len(pages[i:i + 4]))
        for left, right in ((group[3], group[0]), (group[1], group[2])):
            sheet = PageObject.create_blank_page(width=W, height=H)
            if left is not None:
                place(sheet, left, 0)
            if right is not None:
                place(sheet, right, 1)
            writer.add_page(sheet)
        sheets += 1
    with open(out, "wb") as f:
        writer.write(f)
    return sheets


def unexpected_fonts(pdf: Path) -> set[str]:
    """Embedded fonts that are not ours, i.e. Inkscape fell back to a substitute."""
    found = set()
    for page in PdfReader(str(pdf)).pages:
        fonts = (page.get("/Resources") or {}).get("/Font") or {}
        for ref in fonts.values():
            name = str(ref.get_object().get("/BaseFont", "")).split("+")[-1].lstrip("/")
            found.add(name)
    return {f for f in found if not f.startswith(EXPECTED_FONTS)}

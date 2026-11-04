"""One-off: derive the four page templates from the 2026 reference files.

Kept for traceability. After this has run, the files in templates/ are the source of
truth and are edited by hand in Inkscape. Running this again overwrites those edits.

What it does:
  * splits the 4-page October 2026 Inkscape document into one file per page type;
  * reintroduces the 2025 "fact of the day" block and the day-count line on the notes page;
  * gives every field the generator fills a clean, unique inkscape:label;
  * replaces Microsoft fonts with the free fonts in fonts/.

Usage:  python tools/build_templates.py
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
SRC_2026 = ROOT / "reference/2026-october/Planner RaF 2026 - Day on two pages - 4 pages - Dated - 10.svg"
SRC_2025 = ROOT / "reference/2025-templates/Planner RaF 2026 - 02 Left Page Template.svg"
OUT = ROOT / "templates"

SVG = "http://www.w3.org/2000/svg"
INK = "http://www.inkscape.org/namespaces/inkscape"
SODI = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
PLANNER = "https://github.com/rcominelli/my-custom-planner"
LABEL = f"{{{INK}}}label"

FONT_MAP = [
    ("Century Schoolbook", "TeX Gyre Schola"),
    ("Century Gothic", "TeX Gyre Adventor"),
    ("Calibri", "Carlito"),
    ("Brush Script MT", "Caveat"),
]

# output file -> (layer label in the 2026 file, index of the Inkscape page it sits on, relabels by id)
PAGES = {
    "01-month-cover.svg": ("1 Right Page BOM", 0, {
        "text178": "Month Name",
    }),
    "02-day-tasks.svg": ("2 Left page", 1, {
        "text138": "Day Number",
        "text3867-2-3-9": "Month Year Weekday",
        "g2-5-6": "Calendar - This Month",
        "g2-7": "Calendar - Next Month",
        "text133": "Habit - Priority",
        "text134": "Habit - Text",
    }),
    "03-day-notes.svg": ("1 Right Page", 0, {
        "text3864-5-8": "Day Number",
        "text3867-2-3": "Month Year Weekday",
        "text3918": "Notes Title",
        "g3875": "Fact",
        "rect36-2": "Fact - Text frame",
        "g37": "Daily Notes",
        "g36": "Daily Notes Lines",
    }),
    "04-month-end.svg": ("4 Left Page EOM", 3, {
        "text3864-5-1": "Month Name",
        "text3918-5-7": "Notes Title",
    }),
}

# 2025 notes-page elements to bring back: id -> (new label, id of the 2026 parent group).
# Both files use identical group transforms here, so coordinates carry over unchanged.
FROM_2025 = {
    "text3868": ("Fact - Title", "g3875"),
    "text10-5": ("Fact - Date", "g3875"),
    "text3875": ("Fact - Text", "g3875"),
    "text28-1": ("Fact - Source", "g3875"),
    "text3919": ("Day Count", "g37"),
}


def by_id(root, elem_id):
    found = root.xpath("//*[@id=$i]", i=elem_id)
    if len(found) != 1:
        raise RuntimeError(f"expected one element with id {elem_id!r}, found {len(found)}")
    return found[0]


def build(name, layer_label, page_index, relabels, src_2025):
    tree = etree.parse(str(SRC_2026))
    root = tree.getroot()
    named = root.find(f"{{{SODI}}}namedview")
    pages = named.findall(f"{{{INK}}}page")
    x0 = float(pages[page_index].get("x"))

    # keep defs/metadata/namedview and the one layer we want
    keep = None
    for child in list(root):
        if child.tag == f"{{{SVG}}}g" and child.get(f"{{{INK}}}groupmode") == "layer":
            if child.get(LABEL) == layer_label:
                keep = child
            else:
                root.remove(child)
    if keep is None:
        raise RuntimeError(f"layer {layer_label!r} not found")
    keep.set("style", "display:inline")
    if x0:
        keep.set("transform", f"translate({-x0:.5f},0)")

    # single Inkscape page at the origin
    for p in pages[1:]:
        named.remove(p)
    pages[0].set("x", "0")
    pages[0].set("y", "0")
    named.set(f"{{{INK}}}current-layer", keep.get("id"))

    for elem_id, label in relabels.items():
        by_id(root, elem_id).set(LABEL, label)

    if name == "03-day-notes.svg":
        for elem_id, (label, parent_id) in FROM_2025.items():
            el = copy.deepcopy(by_id(src_2025, elem_id))
            el.set(LABEL, label)
            by_id(root, parent_id).append(el)

    if name == "02-day-tasks.svg":
        # Pre-filled habit rows: keep row 1 as the prototype, remember the row pitch,
        # drop rows 2-3 (the generator clones the prototype once per configured habit).
        row1 = float(by_id(root, "text134").get("y"))
        row2 = float(by_id(root, "text20").get("y"))
        pitch = row2 - row1
        for elem_id in ("text133", "text134"):
            by_id(root, elem_id).set(f"{{{PLANNER}}}row-pitch", f"{pitch:.4f}")
        for elem_id in ("text20", "text44"):
            el = by_id(root, elem_id)
            el.getparent().remove(el)

    etree.register_namespace("planner", PLANNER)
    xml = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=False).decode("utf-8")
    for old, new in FONT_MAP:
        xml = xml.replace(old, new)
    # labels must stay unique where the generator looks them up
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(xml, encoding="utf-8")
    labels = re.findall(r'inkscape:label="([^"]+)"', xml)
    print(f"{name}: layer {layer_label!r}, page offset {x0}, {len(labels)} labels")


def main():
    src_2025 = etree.parse(str(SRC_2025)).getroot()
    for name, (layer, page_index, relabels) in PAGES.items():
        build(name, layer, page_index, relabels, src_2025)


if __name__ == "__main__":
    main()

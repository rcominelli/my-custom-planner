"""Fill Inkscape SVG templates by inkscape:label.

Two kinds of text exist in the templates:
  * flowed text (style contains shape-inside): Inkscape wraps and aligns it at export time,
    so we only replace the content and drop the stale x/y of the inner tspans;
  * regular text with one <tspan sodipodi:role="line"> per line: we write one tspan per
    line, and Inkscape recalculates the line positions when it loads the file.
"""
from __future__ import annotations

import base64
import copy
import itertools
from pathlib import Path

from lxml import etree

SVG = "http://www.w3.org/2000/svg"
INK = "http://www.inkscape.org/namespaces/inkscape"
SODI = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
PLANNER = "https://github.com/rcominelli/my-custom-planner"
LABEL = f"{{{INK}}}label"
TSPAN = f"{{{SVG}}}tspan"
ROLE = f"{{{SODI}}}role"

# Days outside the month in the mini calendars
DIM_STYLE = "font-style:italic;-inkscape-font-specification:'TeX Gyre Adventor Italic';fill:#808080"

_uid = itertools.count(1)


class Page:
    def __init__(self, template: Path):
        self.template = template
        self.tree = etree.parse(str(template))
        self.root = self.tree.getroot()

    def find(self, label: str, scope=None):
        found = (scope if scope is not None else self.root).xpath(".//*[@inkscape:label=$l]", l=label,
                                                                  namespaces={"inkscape": INK})
        if len(found) != 1:
            raise KeyError(f"{self.template.name}: expected one element labelled {label!r}, found {len(found)}")
        return found[0]

    def set(self, label: str, value: str, scope=None):
        set_text(self.find(label, scope), value)

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.tree.write(str(path), xml_declaration=True, encoding="UTF-8")


def _text_chain(el):
    """The nested tspans leading to the first non-empty text run (keeps inline styles)."""
    for t in el.iter(TSPAN):
        if (t.text or "").strip():
            chain = [t]
            while chain[-1].getparent() is not el:
                chain.append(chain[-1].getparent())
            return list(reversed(chain))
    return [t for t in el.iter(TSPAN)][:1]


def _shallow(elem, strip_xy=False):
    new = etree.Element(elem.tag, {k: v for k, v in elem.attrib.items()
                                   if not (strip_xy and k in ("x", "y"))})
    return new


def is_flowed(el) -> bool:
    return "shape-inside" in (el.get("style") or "")


def set_text(el, value: str):
    if is_flowed(el):
        if "\n" in value:
            raise ValueError(f"{el.get(LABEL)}: line breaks are not supported in flowed text")
        chain = _text_chain(el)
        for child in list(el):
            el.remove(child)
        el.text = None
        parent = el
        for t in chain:
            new = _shallow(t, strip_xy=True)
            parent.append(new)
            parent = new
        parent.text = value
        return

    lines = [t for t in el if t.tag == TSPAN and t.get(ROLE) == "line"]
    if not lines:
        el.text = value
        return
    proto = lines[0]
    chain = _text_chain(proto) if len(proto) else []
    for child in list(el):
        el.remove(child)
    el.text = None
    for i, line in enumerate(value.split("\n")):
        t = _shallow(proto)
        if i:
            t.set("id", f"{proto.get('id')}-l{i}")
        el.append(t)
        leaf = t
        for c in chain:
            new = _shallow(c)
            leaf.append(new)
            leaf = new
        leaf.text = line


def set_cell(el, value: str, dim: bool):
    """Mini-calendar cell (flowed text): plain for this month, grey italic otherwise."""
    for child in list(el):
        el.remove(child)
    el.text = None
    outer = etree.SubElement(el, TSPAN)
    if dim:
        inner = etree.SubElement(outer, TSPAN, style=DIM_STYLE)
        inner.text = value
    else:
        outer.text = value


def clone_with_offset(el, dy: float):
    """Copy of el (unique ids) shifted down by dy, inserted right after el."""
    new = copy.deepcopy(el)
    n = next(_uid)
    for e in new.iter():
        if e.get("id"):
            e.set("id", f"{e.get('id')}-c{n}")
    tr = new.get("transform")
    new.set("transform", f"translate(0,{dy:.4f})" + (f" {tr}" if tr else ""))
    el.addnext(new)
    return new


def place_image(area, image: Path, px_size: tuple[int, int], mime: str):
    """Insert image scaled to fit the area rectangle, keeping proportions, bottom-right aligned.

    The picture is embedded (data URI), so the page file does not depend on file paths.
    """
    ax, ay = float(area.get("x")), float(area.get("y"))
    aw, ah = float(area.get("width")), float(area.get("height"))
    iw, ih = px_size
    scale = min(aw / iw, ah / ih)
    w, h = iw * scale, ih * scale
    el = etree.Element(f"{{{SVG}}}image", {
        "id": f"picture-{next(_uid)}", LABEL: "Picture",
        "x": f"{ax + aw - w:.4f}", "y": f"{ay + ah - h:.4f}",
        "width": f"{w:.4f}", "height": f"{h:.4f}",
        "preserveAspectRatio": "none",
        "{http://www.w3.org/1999/xlink}href":
            f"data:{mime};base64," + base64.b64encode(image.read_bytes()).decode("ascii")})
    tr = area.get("transform")
    if tr:
        el.set("transform", tr)
    area.addnext(el)
    return el


def row_pitch(el) -> float:
    return float(el.get(f"{{{PLANNER}}}row-pitch"))

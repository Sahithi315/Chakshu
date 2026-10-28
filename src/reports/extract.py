"""Plain-code lab-report extractor (pdfplumber words + coordinates; no OCR, no model).

Two layouts of text-based PDFs are handled:
 - "inline": a line contains  <test name> <value> <unit> <range> [flag]  (one or more results per line)
 - "card":   a drawn box (rect) holding  name / value / unit / "Range a-b | FLAG"  on four lines
Every row keeps page, bbox (x0, top, x1, bottom in PDF points), the source line text and a quote check.
A row whose value is not found in its source line is flagged (quote_ok=False), never dropped.
"""
import re
import pdfplumber

NUM = re.compile(r"^-?\d+(\.\d+)?$")
RANGE = re.compile(r"^(\d+(\.\d+)?-\d+(\.\d+)?|[<>]=?\d+(\.\d+)?)$")
FLAGS = {"IN_RANGE", "HIGH", "LOW"}  # printed in the document; we only copy the text, we do not use it


def lines_of(words, tol=2.5):
    """Group words into lines by vertical position; each line sorted left to right."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(out[-1][0]["top"] - w["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def box(ws):
    return (min(w["x0"] for w in ws), min(w["top"] for w in ws), max(w["x1"] for w in ws), max(w["bottom"] for w in ws))


def outside_listed_range(value, rng):
    """True/False by a plain numeric rule against the range printed in the report; None if not comparable."""
    try:
        v = float(value)
        if rng.startswith(("<=", ">=")): lim, op = float(rng[2:]), rng[:2]
        elif rng[0] in "<>": lim, op = float(rng[1:]), rng[0]
        else:
            lo, hi = (float(x) for x in rng.rsplit("-", 1)); return not (lo <= v <= hi)
    except ValueError:
        return None
    return {"<": v >= lim, "<=": v > lim, ">": v <= lim, ">=": v < lim}[op]


def quote_check(value, source_line):
    """The value must appear as a whole token in its source line (re-run after any correction)."""
    return str(value) in source_line.split()


def make_row(name_ws, val_w, unit, rng, source_ws, page_no, mode, bbox):
    value = val_w["text"]
    source_ws = sorted(source_ws, key=lambda w: (round(w["top"] / 3), w["x0"]))
    line_text = " ".join(w["text"] for w in source_ws)
    return {"test": " ".join(w["text"] for w in name_ws), "value": value, "unit": unit, "reference_range": rng,
            "page": page_no, "bbox": bbox,
            "value_bbox": box([val_w]), "source_line": line_text, "mode": mode,
            "quote_ok": quote_check(value, line_text),
            "range_note": "outside listed range" if outside_listed_range(value, rng) else ""}


def inline_rows(line, page_no):
    rows, start, i = [], 0, 0
    while i < len(line) - 2:
        t = [w["text"] for w in line[i:i + 3]]
        if i > start and NUM.match(t[0]) and not NUM.match(t[1]) and not RANGE.match(t[1]) and RANGE.match(t[2]):
            rows.append(make_row(line[start:i], line[i], t[1], t[2], line, page_no, "inline", box(line[start:i + 3])))
            i += 3
            if i < len(line) and line[i]["text"] in FLAGS:
                i += 1
            start = i
        else:
            i += 1
    return rows


def card_rows(page, words, page_no):
    rows = []
    for r in page.rects:
        inside = [w for w in words if r["x0"] <= (w["x0"] + w["x1"]) / 2 <= r["x1"] and r["top"] <= (w["top"] + w["bottom"]) / 2 <= r["bottom"]]
        ls = lines_of(inside)
        if len(ls) != 4 or ls[3][0]["text"] != "Range" or len(ls[3]) < 2:
            continue
        name, val, unit, rng = ls
        if len(val) == 1 and NUM.match(val[0]["text"]) and RANGE.match(rng[1]["text"]):
            rows.append(make_row(name, val[0], " ".join(w["text"] for w in unit), rng[1]["text"], inside, page_no, "card", box(inside)))
    return rows


def extract_pdf(path):
    rows = []
    with pdfplumber.open(path) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            rows += card_rows(page, words, n)
            for line in lines_of(words):
                rows += inline_rows(line, n)
    return rows


def highlight(path, page_no, bbox, resolution=110):
    """Page image (PIL) with the source bbox outlined and tinted. Uses pdfplumber's renderer (pypdfium2)."""
    with pdfplumber.open(path) as pdf:
        im = pdf.pages[page_no - 1].to_image(resolution=resolution)
        x0, top, x1, bottom = bbox
        im.draw_rect((x0 - 2, top - 2, x1 + 2, bottom + 2), fill=(255, 235, 0, 70), stroke=(220, 0, 0, 255), stroke_width=2)
        return im.annotated.convert("RGB")

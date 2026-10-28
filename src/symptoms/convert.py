"""CSV (id, author, text_marked, source) with [phrase]{S|N|D|V} tags -> JSONL.

Usage: python -m src.symptoms.convert data/symptoms/raw/*.csv --out data/symptoms/all.jsonl
Malformed rows are printed with file, line and reason, and the exit code is 1.
Nothing is dropped silently: bad rows are listed in <out>.errors.txt too.
"""
import argparse, csv, json, re, sys

TAGS = {"S": "SYMPTOM", "N": "NEG_SYMPTOM", "D": "DURATION", "V": "SEVERITY"}
# other tags from the team codebook: kept as plain, unlabelled text (decision of 28 Oct). Any other tag is still an error.
PLAIN_TAGS = set("BFMQUCAETLPH")
TAG_RE = re.compile(r"\[([^\[\]]+)\]\{([^{}]*)\}")


def parse_marked(marked):
    """Return (clean_text, spans). Raises ValueError with a reason on malformed input."""
    text, spans, pos = "", [], 0
    for m in TAG_RE.finditer(marked):
        tag = m.group(2).strip()
        if tag in PLAIN_TAGS:
            text += marked[pos:m.start()] + m.group(1)
            pos = m.end()
            continue
        if tag not in TAGS:
            raise ValueError(f"unknown tag {{{tag}}} on '{m.group(1)}'")
        text += marked[pos:m.start()]
        phrase = m.group(1)
        if phrase != phrase.strip():
            raise ValueError(f"phrase has leading/trailing space: '{phrase}'")
        spans.append({"start": len(text), "end": len(text) + len(phrase), "label": TAGS[tag]})
        text += phrase
        pos = m.end()
    text += marked[pos:]
    # anything left after removing valid tags means unbalanced / nested / untagged brackets
    leftover = TAG_RE.sub("", marked)
    if any(c in leftover for c in "[]{}"):
        raise ValueError("unbalanced or malformed brackets/braces")
    return text, spans


def to_row(r):
    text, spans = parse_marked(r["text_marked"])
    out = []
    for s in spans:  # internal NEG_SYMPTOM is stored as SYMPTOM + negated, per the agreed file format
        if s["label"] == "NEG_SYMPTOM":
            s = {**s, "label": "SYMPTOM", "negated": True}
        out.append(s)
    return {"id": r["id"], "author": r["author"].strip(), "source": r.get("source", ""), "text": text, "spans": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows, errors, seen = [], [], {}
    for path in a.csvs:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            missing = {"id", "author", "text_marked"} - set(rd.fieldnames or [])
            if missing:
                errors.append(f"{path}: missing columns {sorted(missing)}")
                continue
            for i, r in enumerate(rd, start=2):  # line 1 is the header
                where = f"{path}:{i} id={r.get('id')}"
                try:
                    if not (r["author"] or "").strip():
                        raise ValueError("empty author")
                    if not (r["text_marked"] or "").strip():
                        raise ValueError("empty text")
                    row = to_row(r)
                    key = (row["author"], row["id"])
                    if key in seen:
                        raise ValueError(f"duplicate (author,id), first seen at {seen[key]}")
                    seen[key] = where
                    rows.append(row)
                except ValueError as e:
                    errors.append(f"{where}: {e}")
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(a.out + ".errors.txt", "w") as f:
        f.write("\n".join(errors) + ("\n" if errors else ""))
    print(f"{len(rows)} rows written to {a.out}; {len(errors)} malformed")
    for e in errors:
        print("  ERROR", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

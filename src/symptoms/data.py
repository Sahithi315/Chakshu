"""Load, validate, split (by author) and freeze the symptom data."""
import difflib, hashlib, json, re

LABELS = ["SYMPTOM", "NEG_SYMPTOM", "DURATION", "SEVERITY"]
FILE_LABELS = {"SYMPTOM", "DURATION", "SEVERITY"}  # NEG_SYMPTOM is SYMPTOM + negated:true in files


def internal_label(span):
    return "NEG_SYMPTOM" if span["label"] == "SYMPTOM" and span.get("negated") else span["label"]


def load_validated(paths):
    """Return (rows, errors). Rows are normalised to internal labels; every bad row is reported."""
    rows, errors = [], []
    for p in paths:
        for n, line in enumerate(open(p, encoding="utf-8"), 1):
            if not line.strip():
                continue
            where = f"{p}:{n}"
            try:
                r = json.loads(line)
                text, spans = r["text"], r["spans"]
                if not text.strip():
                    raise ValueError("empty text")
                prev_end = 0
                for s in sorted(spans, key=lambda s: s["start"]):
                    if s["label"] not in FILE_LABELS:
                        raise ValueError(f"bad label {s['label']}")
                    if s.get("negated") and s["label"] != "SYMPTOM":
                        raise ValueError("negated only allowed on SYMPTOM")
                    if not (0 <= s["start"] < s["end"] <= len(text)):
                        raise ValueError(f"offsets out of range {s}")
                    if s["start"] < prev_end:
                        raise ValueError(f"overlapping spans at {s['start']}")
                    seg = text[s["start"]:s["end"]]
                    if seg != seg.strip():
                        raise ValueError(f"span has edge whitespace: '{seg}'")
                    prev_end = s["end"]
                rows.append({"id": r.get("id", f"{p}:{n}"), "author": str(r.get("author", "")).strip(),
                             "text": text, "spans": [{"start": s["start"], "end": s["end"], "label": internal_label(s)}
                                                     for s in sorted(spans, key=lambda s: s["start"])]})
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                errors.append(f"{where}: {type(e).__name__}: {e}")
    return rows, errors


def norm(t):
    return re.sub(r"\W+", " ", t.lower()).strip()


def split_by_author(rows, test_authors, sim=0.85):
    """Split by author column (case-insensitive). Drops train rows near-identical to a test row.
    Returns train, test, dropped_near_dups. Raises if a test author is missing."""
    ta = {a.lower() for a in test_authors}
    test = [r for r in rows if r["author"].lower() in ta]
    train = [r for r in rows if r["author"].lower() not in ta]
    missing = ta - {r["author"].lower() for r in test}
    if missing:
        raise SystemExit(f"STOP: test author(s) {sorted(missing)} have no rows")
    assert not ({r["author"].lower() for r in train} & ta)  # holds by construction; kept as a guard
    tn = [norm(r["text"]) for r in test]
    keep, dropped = [], []
    for r in train:
        n = norm(r["text"])
        if any(n == t or difflib.SequenceMatcher(None, n, t).ratio() >= sim for t in tn):
            dropped.append(r)
        else:
            keep.append(r)
    return keep, test, dropped


def summary(rows):
    c = {l: 0 for l in LABELS}
    for r in rows:
        for s in r["spans"]:
            c[s["label"]] += 1
    return {"messages": len(rows), "with_negated": sum(any(s["label"] == "NEG_SYMPTOM" for s in r["spans"]) for r in rows),
            "authors": sorted({r["author"] for r in rows}), **c}


def sha(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def freeze_test(test, authors, path):
    json.dump({"sha256": sha(test), "n": len(test), "authors": authors}, open(path, "w"), indent=1)


def check_frozen(test, path):
    try:
        f = json.load(open(path))
    except FileNotFoundError:
        raise SystemExit(f"STOP: test set not frozen. Run prepare with --freeze")
    if f["sha256"] != sha(test):
        raise SystemExit("STOP: test set changed since it was frozen. Do not edit the test set after freezing.")

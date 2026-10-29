"""No-model baselines: keyword list + simple negation rule.

 - baseline_train: symptom vocabulary = every SYMPTOM/NEG_SYMPTOM span in the TRAIN set (main baseline).
 - baseline: the hand-written list below (weaker, written before any data existed).
 - baseline_negspacy: hand-written list, polarity from negspaCy's Negex (optional).
Duration regex, severity list and negation rule are the same hand-written code in all three.
Never tune any of this on the test set.
"""
import json, re

SYMPTOMS = sorted("""fever|chills|cough|headache|sore throat|chest pain|chest tightness|shortness of breath|breathlessness|
stomach pain|stomach ache|abdominal pain|vomiting|nausea|diarrhoea|diarrhea|constipation|bloating|back pain|joint pain|
body ache|muscle pain|dizziness|fainting|tired|tiredness|fatigue|weakness|weight loss|loss of appetite|swelling|leg swelling|
rash|itching|runny nose|sneezing|blurred vision|palpitations|sweating|wheezing|sleeplessness|insomnia|numbness|toothache|
ear pain|burning urination|frequent urination|excessive thirst|blood|pain""".replace("\n", "").split("|"), key=len, reverse=True)

SEVERITY = ["very severe", "severe", "mild", "moderate", "slight", "unbearable", "terrible", "worst", "intense", "extreme"]
NEG_WORDS = r"\b(no|not|never|without|denies|denied|deny|negative for|free of|absence of|nothing)\b"
BREAKERS = r"\b(but|however|though|although|except)\b|[.;,]"
NEG_WINDOW = 6  # words

DURATION = re.compile(
    r"\b((for|since|over|past|last|from)\s+)?(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|few|several)\s*"
    r"(hours?|days?|weeks?|months?|years?)(\s+ago)?\b|\b(since\s+)?(yesterday|last night|this morning|morning|today)\b", re.I)


def _find(pattern, text, label):
    return [(m.start(), m.end(), label) for m in re.finditer(pattern, text, re.I)]


def _duration_spans(text):
    out = []
    for m in DURATION.finditer(text):
        s, e = m.start(), m.end()
        # keep the duration phrase minimal: drop leading "for"/"since"/"over" etc., which annotators usually leave out
        inner = re.sub(r"^(for|since|over|past|last|from)\s+", "", text[s:e], flags=re.I)
        if inner.lower() in {"morning", "today"}:
            continue
        out.append((e - len(inner), e, "DURATION"))
    return out


def _is_negated(text, start):
    before = text[max(0, start - 80):start]
    cuts = [m.end() for m in re.finditer(BREAKERS, before, re.I)]
    before = before[max(cuts) if cuts else 0:]
    words = before.split()[-NEG_WINDOW:]
    return bool(re.search(NEG_WORDS, " ".join(words), re.I))


def from_train(train_jsonl):
    """Symptom vocabulary from the training spans only; returns predict(text)."""
    vocab = set()
    with open(train_jsonl, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            vocab |= {r["text"][s["start"]:s["end"]].lower() for s in r["spans"] if s["label"] in ("SYMPTOM", "NEG_SYMPTOM")}
    vocab = sorted(vocab, key=len, reverse=True)
    return lambda text: predict(text, vocab)


def predict(text, symptoms=None):
    spans, taken = [], []
    for s, e, l in _duration_spans(text) + _find(r"\b(" + "|".join(map(re.escape, SEVERITY)) + r")\b", text, "SEVERITY"):
        spans.append((s, e, l)); taken.append((s, e))
    for kw in symptoms or SYMPTOMS:  # longest first; skip overlaps
        for m in re.finditer(r"\b" + re.escape(kw) + r"\b", text, re.I):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            spans.append((m.start(), m.end(), "NEG_SYMPTOM" if _is_negated(text, m.start()) else "SYMPTOM"))
    return [{"start": s, "end": e, "label": l} for s, e, l in sorted(spans)]


def predict_negspacy(text, _cache={}):
    """Same keyword entities, but polarity decided by negspaCy's Negex. Raises ImportError if unavailable."""
    if not _cache:
        import spacy
        from negspacy.negation import Negex  # noqa: F401  (registers the factory)
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        ruler = nlp.add_pipe("entity_ruler")
        ruler.add_patterns([{"label": "SYM", "pattern": [{"LOWER": w} for w in kw.split()]} for kw in SYMPTOMS])
        nlp.add_pipe("negex", config={"ent_types": ["SYM"]})
        _cache["nlp"] = nlp
    doc = _cache["nlp"](text)
    sym = [{"start": e.start_char, "end": e.end_char, "label": "NEG_SYMPTOM" if e._.negex else "SYMPTOM"} for e in doc.ents]
    others = [p for p in predict(text) if p["label"] in ("DURATION", "SEVERITY")]
    return sorted(sym + others, key=lambda p: p["start"])

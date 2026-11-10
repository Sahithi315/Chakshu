"""Generate synthetic Hindi / Hinglish symptom messages with exact character spans.

python tools/generate_hindi_symptoms.py        # writes data/symptoms/hindi/{all,train,dev}.jsonl

1500 messages: 40% Roman Hindi/Hinglish, 30% Devanagari, 30% English rows copied from data/symptoms/split/train.jsonl.
15% of all messages (Hindi only) are a dev split that uses other sentence patterns and 8 symptoms never seen in training.
Synthetic text from our own lexicon: a sanity check for the pipeline, not a measure of real-world performance.
"""
import json, random, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.symptoms import hindi
from src.symptoms.data import load_validated, split_by_author, summary

OUT = Path("data/symptoms/hindi")
HELD_OUT = {"tooth pain", "hand pain", "numbness", "tingling", "cramps", "sneezing", "palpitations", "burning eyes"}
# {S1..S3} symptom, {N1,N2} negated symptom, {D} duration, {V} severity. Literal words are Roman; Devanagari rows translate them.
TRAIN_PATTERNS = [
    "mujhe {D} se {S1} hai", "{S1} hai {D} se", "mujhe {S1} hai, {N1} nahi hai", "{V} {S1} ho raha hai", "mujhe {S1} aur {S2} hai",
    "{D} se {V} {S1} hai lekin {N1} nahi hai", "{N1} nahi hai par {S1} hai", "mera {S1} {V} hai", "{S1} hai, {S2} bhi hai",
    "bina {N1} ke {S1} hai", "{S1}, {S2} aur {S3} hai", "{D} se {S1} hai aur {N1} nahi", "mujhe koi {N1} nahi hai",
    "{S1} {D} se ho raha hai", "mujhe {S1} hai {D} se", "{D} se {S1} aur {S2} hai", "{S1} {V} hai, {N1} nahi",
    "mujhe {N1} nahi hai lekin {S1} hai", "{N1} nahi hai, {N2} bhi nahi hai", "{S1} hai magar {N1} nahi hai", "mere {S1} {V} hai {D} se",
    "{D} se {N1} nahi hai, bas {S1} hai", "mujhe {S1} ho raha hai aur {S2} bhi", "{V} {S1}, {S2} bhi hai", "{S1} ho rahi hai {D} se, {N1} nahi",
    "mujhe {V} {S1} hai", "{S1} nahi hai par {S2} hai", "{D} se mujhe {S1} hai", "{S1} hai lekin {S2} nahi hai",
    "{S1} ki dikkat hai {D} se", "{S1} hai aur {S2} bhi, {N1} nahi hai", "{N1} nahi hai, {S1} hai {V}", "{D} se {S1}, {S2} aur {N1} nahi",
]
DEV_PATTERNS = [
    "{D} pehle se {S1} shuru hua hai", "{S1} ke saath {S2} bhi hai, {N1} nahi", "ab bas {S1} {V} hai", "{N1} to nahi hai magar {S1} hai {D} se",
    "{V} {S1} hai aur {S2} bhi, {N1} nahi hai", "mujhe {S1} ki shikayat hai {D} se", "{S1} aur {S2} dono hain, {D} se",
    "sirf {S1} hai, {N1} nahi hai", "{D} se {S1} aur {S2} ki shikayat hai", "{S1} to hai par {N1} nahi",
]
FILLERS = ["doctor sahab,", "namaste,", "please dekhiye,"]
SUFFIXES = ["please", "dekhiye"]
WORDS = {w: d for w, d in zip(
    "mujhe mera mere hai hain se nahi aur bhi lekin par magar koi bina ke ho raha rahi bas sirf to ki dikkat shikayat saath pehle dono ab shuru hua doctor sahab namaste please dekhiye".split(),
    "मुझे मेरा मेरे है हैं से नहीं और भी लेकिन पर मगर कोई बिना के हो रहा रही बस सिर्फ तो की दिक्कत शिकायत साथ पहले दोनों अब शुरू हुआ डॉक्टर साहब नमस्ते प्लीज़ देखिए".split())}
UNITS = {"roman": ["din", "din", "hafte", "mahine", "ghante", "saal"], "deva": ["दिन", "दिन", "हफ्ते", "महीने", "घंटे", "साल"]}
TIMES = {"roman": ["kal", "parso", "subah", "raat", "kal raat"], "deva": ["कल", "परसों", "सुबह", "रात", "कल रात"]}
NUMS = {"roman": "ek do teen char paanch saat das".split(), "deva": "एक दो तीन चार पाँच सात दस".split()}
DEVA_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
SEVS = {"roman": ["bahut", "bahut zyada", "thoda", "thoda sa", "halka", "tez", "bahut tez", "kaafi", "zyada", "severe", "mild", "very"],
        "deva": ["बहुत", "बहुत ज्यादा", "थोड़ा", "थोड़ा सा", "हल्का", "तेज", "बहुत तेज", "काफी", "ज्यादा"]}
BAD_WORDS = hindi.AFFS | {"rahi", "raha", "rahe", "pad", "badh", "रहा", "रही"}  # verbs that would clash with the pattern's own "hai"
SYMPTOMS = {}  # english -> {"roman": [...], "deva": [...], "english": [...]}
for eng, v in hindi.LEXICON.items():
    clean = lambda vs: [x for x in vs + ([eng] if vs is v["english"] else []) if not set(map(hindi.norm, x.split())) & BAD_WORDS]
    SYMPTOMS[eng] = {k: clean(v[k]) for k in ("roman", "deva", "english")}
# 'bhookh nahi lagti' style variants: the nahi is part of the complaint, so they only go in positive slots
INSIDE = {e for e, v in SYMPTOMS.items() if any(set(map(hindi.norm, x.split())) & hindi.NEGS for k in v for x in v[k])}


def symptom(rng, script, names, negated=False):
    """One spelling of a randomly chosen symptom; negated slots never get a 'nahi'-inside spelling."""
    eng = rng.choice(names)
    v = SYMPTOMS[eng]
    pool = v["deva"] if script == "deva" else v["roman"] if v["roman"] and rng.random() < 0.7 else v["english"]
    pool = pool or v["english"]
    if negated:
        pool = [x for x in pool if not set(map(hindi.norm, x.split())) & hindi.NEGS]
    return rng.choice(pool) if pool else None


def duration(rng, script):
    if rng.random() < 0.25:
        return rng.choice(TIMES[script])
    n = str(rng.choice([1, 2, 2, 3, 3, 4, 5, 7, 10, 15]))
    n = rng.choice([n, n, rng.choice(NUMS[script])])
    return (n.translate(DEVA_DIGITS) if script == "deva" and rng.random() < 0.3 else n) + " " + rng.choice(UNITS[script])


def noise(rng, s):
    """Spelling noise: dropped vowel, doubled letter or missing space (Roman text only)."""
    kind = rng.choice(["drop", "double", "space"])
    if kind == "space" and " " in s:
        i = rng.choice([m.start() for m in re.finditer(" ", s)]); return s[:i] + s[i + 1:]
    idx = [i for i, c in enumerate(s) if i > 0 and c.isalpha() and c.isascii() and s[i - 1].isalpha()]
    if len(s) < 4 or not idx:
        return s
    i = rng.choice(idx)
    return s[:i] + s[i + 1:] if kind == "drop" and s[i] in "aeiou" else s[:i] + s[i] + s[i:] if kind == "double" else s


def message(rng, pattern, script, names):
    """Return (text, spans). Spans are taken from the segments as they are concatenated, so offsets are exact."""
    segs, used = [], set()
    def pick(slot):
        if slot[0] == "D": return duration(rng, script), "DURATION"
        if slot[0] == "V": return rng.choice(SEVS[script]), "SEVERITY"
        neg = slot[0] == "N"
        while True:
            name = rng.choice([n for n in names if n in INSIDE] if not neg and rng.random() < 0.2 and any(n in INSIDE for n in names) else names)
            text = symptom(rng, script, [name], neg)
            if name not in used and text:
                used.add(name); return text, "SYMPTOM"
    pre = [(rng.choice(FILLERS) + " ", None, 0)] if rng.random() < 0.2 else []
    for part in re.split(r"(\{\w+\})", pattern):
        if part.startswith("{"):
            text, label = pick(part[1:-1])
            segs.append((text, label, part[1] == "N"))
        elif part:
            segs.append((part, None, 0))
    if rng.random() < 0.1:
        segs.append((" " + rng.choice(SUFFIXES), None, 0))
    segs = pre + segs
    if script == "deva":
        segs = [(re.sub(r"[a-z]+", lambda m: WORDS[m.group()], t) if l is None else t, l, n) for t, l, n in segs]
    if script == "roman" and rng.random() < 0.3:
        i = rng.randrange(len(segs)); segs[i] = (noise(rng, segs[i][0]), segs[i][1], segs[i][2])
    text, spans = "", []
    for t, label, neg in segs:
        if label and t.strip():
            lead = len(t) - len(t.lstrip())
            span = {"start": len(text) + lead, "end": len(text) + len(t.rstrip()), "label": label}
            if neg: span["negated"] = True
            spans.append(span)
        text += t
    return text, spans


def build(rng, n, patterns, script, names, dev, seen):
    rows = []
    while len(rows) < n:
        pattern = rng.choice(patterns)
        pool = list(names)
        if dev:  # about 40% of symptoms come from words never used in training
            pool = [x for x in names if x in HELD_OUT] * 6 + [x for x in names if x not in HELD_OUT] * 2
        text, spans = message(rng, pattern, script, pool)
        if text in seen: continue
        seen.add(text)
        rows.append({"id": f"hi_{'dev' if dev else 'train'}_{script}_{len(rows):04d}", "author": "synthetic_hindi", "source": "synthetic_hindi",
                     "text": text, "spans": spans})
    return rows


def main():
    for p in DEV_PATTERNS + TRAIN_PATTERNS:
        re.sub(r"[a-z]+", lambda m: WORDS[m.group()], re.sub(r"\{\w+\}", "", p))  # KeyError = a word has no Devanagari form
    rng, seen = random.Random(2026), set()
    train_names = [e for e in SYMPTOMS if e not in HELD_OUT]
    rows = (build(rng, 471, TRAIN_PATTERNS, "roman", train_names, False, seen) + build(rng, 354, TRAIN_PATTERNS, "deva", train_names, False, seen)
            + build(rng, 129, DEV_PATTERNS, "roman", list(SYMPTOMS), True, seen) + build(rng, 96, DEV_PATTERNS, "deva", list(SYMPTOMS), True, seen))
    english = [json.loads(l) for l in open("data/symptoms/split/train.jsonl", encoding="utf-8")]
    for r in rng.sample(english, 450):  # back to the file format: NEG_SYMPTOM -> SYMPTOM + negated
        spans = [{"start": s["start"], "end": s["end"], "label": "SYMPTOM" if s["label"] == "NEG_SYMPTOM" else s["label"],
                  **({"negated": True} if s["label"] == "NEG_SYMPTOM" else {})} for s in r["spans"]]
        rows.append({"id": "en_" + r["id"], "author": r["author"], "source": "llm_english", "text": r["text"], "spans": spans})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "all.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    good, errors = load_validated([OUT / "all.jsonl"])
    print(f"{len(rows)} rows generated, {len(errors)} bad rows")
    for e in errors:
        print("BAD", e)
    if errors:
        sys.exit("STOP: fix the generator; no row was skipped silently.")
    dev = [r for r in good if r["id"].startswith("hi_dev_")]
    train, _, dropped = split_by_author([dict(r, author="dev" if r in dev else r["author"]) for r in good], ["dev"])
    for name, part in (("train", train), ("dev", dev)):
        with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps({k: v for k, v in r.items()}, ensure_ascii=False) + "\n" for r in part)
    print("train:", summary(train)); print("dev:  ", summary(dev)); print("near-duplicates dropped from train:", len(dropped))


if __name__ == "__main__":
    main()

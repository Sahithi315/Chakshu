"""Rule-based Hindi / Hinglish symptom extractor (Devanagari and Roman letters).

    from src.symptoms.hindi import looks_hindi, extract
    extract("mujhe 3 din se bukhar hai, khansi nahi hai")

Same output shape as infer.structure(), plus an "english" name on each symptom.
"""
import csv
import re
import unicodedata
from pathlib import Path

LEXICON_CSV = Path(__file__).resolve().parents[2] / "data" / "symptoms" / "hindi" / "lexicon_review.csv"  # edit this file to change the lexicon


def load_lexicon(path=LEXICON_CSV):
    """english name -> {"deva": [...], "roman": [...], "english": [...]} from the review CSV (variants separated by ;)."""
    with open(path, encoding="utf-8", newline="") as f:
        return {r["english"]: {"deva": r["devanagari"].split(";") if r["devanagari"] else [],
                               "roman": r["roman"].split(";") if r["roman"] else [],
                               "english": r["english_variants"].split(";") if r["english_variants"] else []} for r in csv.DictReader(f)}


LEXICON = load_lexicon()
NUMBERS = set("ek do teen char chaar paanch panch chhe chheh saat aath nau das barah pandrah bees tees ten एक दो तीन चार पाँच पांच छह छः सात आठ नौ दस बारह पंद्रह बीस".split())
UNITS = set("din dino hafta hafte haftah mahina mahine mahinon saal sal ghanta ghante ghanton day days week weeks month months year years hour hours hr hrs "
            "दिन दिनों हफ्ता हफ्ते सप्ताह महीना महीने महीनों साल घंटा घंटे घंटों".split())
TIME_WORDS = set("kal parso subah raat shaam aaj कल परसों सुबह रात शाम आज".split())
SEVERITY = ["bahut zyada", "bahut tez", "thoda sa", "bahut", "zyada", "jyada", "thoda", "halka", "tez", "kaafi", "severe", "mild", "very",
            "बहुत ज्यादा", "बहुत तेज", "थोड़ा सा", "बहुत", "ज्यादा", "थोड़ा", "हल्का", "तेज", "काफी"]
NEGATION = set("nahi nahin nai na nhi bina mat no not नहीं नही ना बिना".split())
BREAKS = set("lekin par magar but aur kintu लेकिन पर मगर और".split())
AFFIRM = set("hai hain hu hoon है हैं हूं हूँ".split())  # a plain "is/are" ends a negation window
FUNCTION_WORDS = set("mujhe mujhko hai hain ho hoon raha rahi rahe se din nahi nahin kal bahut thoda mera meri mere ka ki ke mein me aur hua hui "
                     "hota hoti tha thi lagta lag rahe है हैं मुझे मेरा मेरी में और से नहीं बहुत हो रहा रही था थी".split())


def norm(word):
    """Lowercase, drop nukta, unify chandrabindu, collapse doubled Roman letters (bukhaar, khaansi)."""
    w = unicodedata.normalize("NFC", word).lower().replace("़", "").replace("ँ", "ं")
    return re.sub(r"([a-z])\1+", r"\1", w)


def _build():
    """phrase (tuple of normalised words) -> (english, is_english_spelling)."""
    table = {}
    for english, v in LEXICON.items():
        for spellings, is_eng in ((v["deva"] + v["roman"], False), (v["english"] + [english], True)):
            for sp in spellings:
                table[tuple(norm(w) for w in sp.split())] = (english, is_eng)
    return table


TABLE = _build()
MAX_WORDS = max(map(len, TABLE))
SEVERITY_TABLE = {tuple(norm(w) for w in s.split()) for s in SEVERITY}
SETS = [{norm(w) for w in s} for s in (NUMBERS, UNITS, TIME_WORDS, NEGATION, BREAKS, AFFIRM, FUNCTION_WORDS)]
NUMS, UNITS_N, TIMES, NEGS, BRKS, AFFS, FUNCS = SETS
INSIDE = {k: v for k, v in TABLE.items() if set(k) & NEGS}  # 'bhookh nahi lagti': the nahi is part of the complaint
DIGITS = re.compile(r"^[0-9०-९]+$")


def tokens(text):
    return [(m.start(), m.end(), norm(m.group())) for m in re.finditer(r"[\wऀ-ॿ]+", text)]


def looks_hindi(text):
    if re.search(r"[ऀ-ॿ]", text):
        return True
    toks = tokens(text)
    words = [t[2] for t in toks]
    hits = sum(w in FUNCS for w in words)
    # one function word plus a Hindi-spelled symptom ("bukhar hai") also counts
    return hits >= 2 or (hits >= 1 and any(TABLE.get(tuple(words[i:i + n]), (0, True))[1] is False
                                           for i in range(len(words)) for n in range(1, MAX_WORDS + 1)))


def _phrases(words, table, used):
    """Longest-first, left-to-right phrase matches as (first_token, last_token, value)."""
    out, i = [], 0
    while i < len(words):
        for n in range(min(MAX_WORDS, len(words) - i), 0, -1):
            hit = tuple(words[i:i + n])
            if hit in table and not any(j in used for j in range(i, i + n)):
                out.append((i, i + n - 1, table[hit]))
                used.update(range(i, i + n))
                i += n - 1
                break
        i += 1
    return out


def _durations(toks, used):
    out, i = [], 0
    while i < len(toks):
        j = i
        while j < len(toks) and (toks[j][2] in NUMS or DIGITS.match(toks[j][2])):
            j += 1
        if j > i and j < len(toks) and toks[j][2] in UNITS_N:          # "3 din", "do teen hafte"
            out.append((i, j))
        else:
            k = i
            while k < len(toks) and toks[k][2] in TIMES:
                k += 1
            if k > i and k < len(toks) and toks[k][2] in ("se", "से"):
                out.append((i, k - 1))                                     # "kal se", "kal raat se"
                j = k - 1
            else:
                i += 1
                continue
        used.update(range(i, j + 1))
        i = j + 1
    return out


def _negated(toks, first, last, text, other_symptoms):
    """Cue within 3 words after or 4 before; stop at clause breaks, plain 'hai', or another symptom."""
    def walk(rng, limit, gap):
        for steps, j in enumerate(rng, 1):
            if steps > limit or j in other_symptoms or toks[j][2] in BRKS or toks[j][2] in AFFS or re.search(r"[,.;:!?।]", gap(j)):
                return False
            if toks[j][2] in NEGS:
                return True
        return False
    return (walk(range(last + 1, len(toks)), 3, lambda j: text[toks[last][1]:toks[j][0]])
            or walk(range(first - 1, -1, -1), 4, lambda j: text[toks[j][1]:toks[first][0]]))


def extract(text):
    toks = tokens(text)
    words = [t[2] for t in toks]
    used = set()
    res = {"text": text, "symptoms": [], "durations": [], "severities": []}
    for a, b in _durations(toks, used):
        res["durations"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1]})
    found = _phrases(words, TABLE, used)
    symptom_idx = {j for a, b, _ in found for j in range(a, b + 1)}
    for a, b, (english, _) in found:
        own = set(range(a, b + 1))
        res["symptoms"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1], "english": english,
                                "negated": tuple(words[a:b + 1]) not in INSIDE and _negated(toks, a, b, text, symptom_idx - own)})
    for a, b, _ in _phrases(words, {k: 1 for k in SEVERITY_TABLE}, used):
        res["severities"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1]})
    for key in ("symptoms", "durations", "severities"):
        res[key].sort(key=lambda s: s["start"])
    return res


def keep_inside_negation(text, symptoms):
    """Post-rule for model output: 'bhookh nahi lagti' is one positive symptom, whatever the model tagged."""
    toks = tokens(text)
    found = [(toks[a][0], toks[b][1], v[0]) for a, b, v in _phrases([t[2] for t in toks], INSIDE, set())]
    kept = [s for s in symptoms if not any(s["start"] < end and start < s["end"] for start, end, _ in found)]
    return sorted(kept + [{"text": text[start:end], "start": start, "end": end, "english": eng, "negated": False} for start, end, eng in found],
                  key=lambda s: s["start"])

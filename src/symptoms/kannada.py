"""Rule-based Kannada symptom extractor (Kannada script and Roman letters). Early version, no native-speaker check yet.

    from src.symptoms.kannada import looks_kannada, extract
    extract("nange 3 dina inda jwara ide, kemmu illa")

Same output shape as hindi.extract(): symptoms (with "english" and "negated"), durations, severities.
"""
import csv
import re
import unicodedata
from pathlib import Path
from .hindi import _phrases, MAX_WORDS as HINDI_MAX_WORDS

LEXICON_CSV = Path(__file__).resolve().parents[2] / "data" / "symptoms" / "kannada" / "lexicon_review.csv"  # edit this file to change the lexicon

NUMBERS = set("ondu ond eradu erdu mooru muru naalku nalku aidu aaru elu entu ombattu hattu "
              "ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು ಹತ್ತು".split())
UNITS = set("dina dinagalu divasa vaara vara tingalu tingla varsha gante ganta day days week weeks month months year years hour hours "
            "ದಿನ ದಿನಗಳು ದಿವಸ ವಾರ ತಿಂಗಳು ವರ್ಷ ಗಂಟೆ".split())
TIME_WORDS = set("ninne monne beligge belagge raatri ratri sanje ivattu ನಿನ್ನೆ ಮೊನ್ನೆ ಬೆಳಿಗ್ಗೆ ರಾತ್ರಿ ಸಂಜೆ ಇವತ್ತು".split())
FROM = set("inda ಇಂದ since".split())
SEVERITY = ["tumba jaasti", "thumba jaasti", "tumba", "thumba", "tumbaa", "jaasti", "jasti", "swalpa", "kammi", "hecchu", "severe", "mild", "very",
            "ತುಂಬಾ ಜಾಸ್ತಿ", "ತುಂಬಾ", "ಜಾಸ್ತಿ", "ಸ್ವಲ್ಪ", "ಕಮ್ಮಿ", "ಹೆಚ್ಚು"]
NEGATION = set("illa ila ilva ilvaa ille alla bandilla aagilla agilla ಇಲ್ಲ ಇಲ್ಲಾ ಇಲ್ವ ಅಲ್ಲ".split())
NEG_SUFFIXES = ("ila", "ilva", "ಿಲ್ಲ", "ಿಲ್ವ", "ಇಲ್ಲ", "ಿಲ್ಲಾ")  # bandilla, aagilla, ಬಂದಿಲ್ಲ (after norm)
NEG_BEFORE = set("no not without".split())  # mixed text: "no jwara"
BREAKS = set("aadre aadare adre adare matte but ಆದರೆ ಆದ್ರೆ ಮತ್ತೆ".split())
AFFIRM = set("ide idhe aagtide agtide aaguthide bartide bandide aagide ಇದೆ ಆಗುತ್ತಿದೆ ಬರ್ತಿದೆ ಬಂದಿದೆ ಆಗಿದೆ".split())  # "is" ends a negation window
ABSENCE = {"loss of appetite", "sleeplessness"}  # named by an absence (hasivu aagalla, nidde barolla): never negated
MARKERS = set("nange nanage nangu nanna ide idhe illa inda dina dinadinda tumba thumba swalpa aagtide agtide aaguthide novu noovu "
              "barta bartide bandide aagide jaasti ninne aadre".split())
# raw word endings split off as their own token when the rest is a known word: jwaravilla, ಕೆಮ್ಮಿಲ್ಲ, dinadinda, ನಿನ್ನೆಯಿಂದ
SPLIT = [(s, "ila") for s in ("villa", "illa", "ilva", "ವಿಲ್ಲ", "ಿಲ್ಲ", "ಿಲ್ವ")] + [(s, "inda") for s in ("dinda", "yinda", "inda", "ರಿಂದ", "ದಿಂದ", "ಯಿಂದ", "ಿಂದ", "ಇಂದ")]
LOCATIVE = ("yali", "dali", "nali", "ali", "ಯಲ್ಲಿ", "ದಲ್ಲಿ", "ನಲ್ಲಿ", "ಲ್ಲಿ")  # hotteyalli -> hotte, ಎದೆಯಲ್ಲಿ -> ಎದೆ
KANNADA = re.compile(r"[ಀ-೿]")
DIGITS = re.compile(r"^[0-9೦-೯]+$")


def norm(word):
    """Lowercase, collapse doubled Roman letters (kemmu, illa), drop a locative ending."""
    w = re.sub(r"([a-z])\1+", r"\1", unicodedata.normalize("NFC", word).lower())
    for suf in LOCATIVE:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def _key(phrase):
    return tuple(norm(w) for w in phrase.split())


with open(LEXICON_CSV, encoding="utf-8", newline="") as f:
    LEXICON = list(csv.DictReader(f))
TABLE = {}  # phrase key -> (english, is_english_spelling)
for r in LEXICON:
    for col, is_eng in (("kannada", False), ("roman", False), ("english_variants", True)):
        for sp in filter(None, r[col].split(";")):
            TABLE[_key(sp)] = (r["english"], is_eng)
    TABLE[_key(r["english"])] = (r["english"], True)
assert max(map(len, TABLE)) <= HINDI_MAX_WORDS  # _phrases looks at most that many words
SEVERITY_TABLE = {_key(s): 1 for s in SEVERITY}
NUMS, UNITS_N, TIMES, NEGS, BRKS, AFFS, MARKS = ({norm(w) for w in s} for s in (NUMBERS, UNITS, TIME_WORDS, NEGATION, BREAKS, AFFIRM, MARKERS))
ROMAN_SPELLED = {k: 1 for k, (_, is_eng) in TABLE.items() if not is_eng and not KANNADA.search(k[0])}
KNOWN = {k[0] for k in TABLE if len(k) == 1} | {w for k in TABLE for w in k} | UNITS_N | TIMES


def tokens(text):
    """(start, end, normalised word); a known word glued to illa/inda becomes two tokens."""
    out = []
    for m in re.finditer(r"[\wಀ-೿]+", text):
        raw, n = unicodedata.normalize("NFC", m.group()).lower(), norm(m.group())
        for suf, cue in SPLIT if n not in KNOWN else []:
            stem = raw[:-len(suf)]
            hit = next((c for c in (norm(stem), norm(stem + "u"), norm(stem + "ು")) if c in KNOWN), None) if raw.endswith(suf) and stem else None
            if hit:
                out += [(m.start(), m.start() + len(stem), hit), (m.start() + len(stem), m.end(), cue)]
                break
        else:
            out.append((m.start(), m.end(), n))
    return out


def is_neg(w):
    return w in NEGS or (len(w) > 3 and w.endswith(NEG_SUFFIXES))


def markers(text):
    """Kannada-script words, common Roman-Kannada words, and Roman Kannada-spelled symptoms ('vaanti', 'hasivu aagalla')."""
    words = [t[2] for t in tokens(text)]
    return sum(bool(KANNADA.search(w)) or w in MARKS for w in words) + len(_phrases(words, ROMAN_SPELLED, set()))


def looks_kannada(text):
    return bool(KANNADA.search(text)) or markers(text) >= 2


def _durations(toks, used):
    """'3 dina inda', 'eradu vaara', 'ninne raatri inda'. The span excludes inda."""
    out, i = [], 0
    while i < len(toks):
        j = i
        while j < len(toks) and (toks[j][2] in NUMS or DIGITS.match(toks[j][2])):
            j += 1
        if j > i and j < len(toks) and toks[j][2] in UNITS_N:
            out.append((i, j))
        else:
            k = i
            while k < len(toks) and toks[k][2] in TIMES:
                k += 1
            if k > i and k < len(toks) and toks[k][2] in FROM:
                out.append((i, k - 1))
                j = k - 1
            else:
                i += 1
                continue
        used.update(range(i, j + 1))
        i = j + 1
    return out


def _negated(toks, first, last, text, other_symptoms):
    """Kannada negates after the symptom ('jwara illa', 'vaanti aagilla'): cue within 3 words after,
    or 'no'/'not' within 3 before; stop at clause breaks, 'ide', or another symptom."""
    def walk(rng, cue, gap):
        for steps, j in enumerate(rng, 1):
            if steps > 3 or j in other_symptoms or toks[j][2] in BRKS or toks[j][2] in AFFS or re.search(r"[,.;:!?।]", gap(j)):
                return False
            if cue(toks[j][2]):
                return True
        return False
    return (walk(range(last + 1, len(toks)), is_neg, lambda j: text[toks[last][1]:toks[j][0]])
            or walk(range(first - 1, -1, -1), NEG_BEFORE.__contains__, lambda j: text[toks[j][1]:toks[first][0]]))


def extract(text):
    toks = tokens(text)
    words = [t[2] for t in toks]
    used = set()
    res = {"text": text, "symptoms": [], "durations": [], "severities": []}
    for a, b in _durations(toks, used):
        res["durations"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1]})
    severity_idx = {k for a, b, _ in _phrases(words, SEVERITY_TABLE, set()) for k in range(a, b + 1)}
    found = _phrases(words, TABLE, used, severity_idx)  # 'tale tumba novu' -> headache, severity 'tumba'
    symptom_idx = {j for a, b, _ in found for j in range(a, b + 1)}
    for a, b, (english, _) in found:
        res["symptoms"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1], "english": english,
                                "negated": english not in ABSENCE and _negated(toks, a, b, text, symptom_idx - set(range(a, b + 1)))})
    for a, b, _ in _phrases(words, SEVERITY_TABLE, used):
        res["severities"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1]})
    for key in ("symptoms", "durations", "severities"):
        res[key].sort(key=lambda s: s["start"])
    return res

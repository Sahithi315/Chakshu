"""Rule-based Hindi / Hinglish symptom extractor (Devanagari and Roman letters).

    from src.symptoms.hindi import looks_hindi, extract
    extract("mujhe 3 din se bukhar hai, khansi nahi hai")

Same output shape as infer.structure(), plus an "english" name on each symptom.
"""
import re
import unicodedata

# english name: "hindi spellings | english spellings" (the english name itself always matches)
LEXICON = {
    "fever": "बुखार, bukhar, bukhaar, bukar, bhukar, taap, tap, jwar, ज्वर | temperature",
    "headache": "सिर दर्द, सिरदर्द, सर दर्द, सिर में दर्द, सर में दर्द, sar dard, sir dard, sardard, sirdard, sar me dard, sir me dard, sar mein dard, sir mein dard | head pain",
    "stomach pain": "पेट दर्द, पेट में दर्द, pet dard, pet me dard, pet mein dard, pait dard, pet ma dard | stomach ache, stomach pain",
    "cough": "खांसी, खाँसी, khansi, khaansi, khasi, khaasi, kasi | cough",
    "cold": "जुकाम, सर्दी, zukam, jukam, zukaam, sardi, nazla | cold",
    "runny nose": "नाक बहना, naak behna, naak beh rahi, naak beh raha, naak bah rahi | runny nose",
    "blocked nose": "नाक बंद, naak band, naak bandh | blocked nose",
    "sore throat": "गले में दर्द, गला खराब, gale me dard, gale mein dard, gala dard, gala kharab, gale me kharash | sore throat, throat pain",
    "vomiting": "उल्टी, ulti, ulty, ulti hona, ulti jaisa | vomiting, vomit",
    "nausea": "जी मिचलाना, मिचली, ji michlana, jee michlana, ji machlana, ji michlata | nausea",
    "loose motions": "दस्त, पेट खराब, dast, patle dast, pet kharab, pet kharaab | loose motions, loose motion, diarrhea, diarrhoea",
    "dizziness": "चक्कर आना, चक्कर, chakkar aana, chakkar aa rahe hain, chakkar, sir ghoomna, sar ghumna | dizziness, dizzy",
    "weakness": "कमजोरी, कमज़ोरी, kamzori, kamjori, kamzoori | weakness",
    "tiredness": "थकान, थकावट, thakan, thakaan, thakawat | tiredness, fatigue",
    "body ache": "बदन दर्द, शरीर दर्द, बदन में दर्द, badan dard, sharir dard, badan me dard, badan mein dard, badan toot raha | body ache, body pain",
    "breathlessness": "सांस फूलना, सांस लेने में दिक्कत, saans phoolna, saans phoolti, saans lene me dikkat, saans me takleef, dam phoolna | breathlessness, shortness of breath",
    "chest pain": "सीने में दर्द, छाती में दर्द, seene me dard, seene mein dard, chhati me dard, chati me dard | chest pain",
    "burning urination": "पेशाब में जलन, peshab me jalan, peshab mein jalan, urine me jalan | burning urination",
    "frequent urination": "बार बार पेशाब, baar baar peshab | frequent urination",
    "itching": "खुजली, khujli, khujali | itching",
    "swelling": "सूजन, sujan, soojan | swelling",
    "loss of appetite": "भूख नहीं लगती, भूख कम, bhookh nahi lagti, bhook nahi lagti, bhookh kam, bhook kam | loss of appetite",
    "sleeplessness": "नींद नहीं आती, neend nahi aati, neend kam | insomnia, sleeplessness",
    "back pain": "कमर दर्द, कमर में दर्द, पीठ दर्द, kamar dard, kamar me dard, kamar mein dard, peeth dard, peeth me dard | back pain, backache",
    "joint pain": "जोड़ों में दर्द, jodon me dard, jodo me dard, jodon mein dard | joint pain",
    "knee pain": "घुटने में दर्द, ghutne me dard, ghutne mein dard | knee pain",
    "neck pain": "गर्दन में दर्द, गर्दन दर्द, gardan me dard, gardan dard | neck pain",
    "shoulder pain": "कंधे में दर्द, kandhe me dard, kandhe mein dard | shoulder pain",
    "leg pain": "पैर में दर्द, टांग में दर्द, pair me dard, taang me dard, per me dard | leg pain",
    "hand pain": "हाथ में दर्द, haath me dard, hath me dard | hand pain",
    "ear pain": "कान में दर्द, कान दर्द, kaan me dard, kaan dard, kaan mein dard | ear pain, earache",
    "tooth pain": "दांत दर्द, दांत में दर्द, daant dard, daant me dard, dant dard | toothache, tooth pain",
    "eye pain": "आंख में दर्द, aankh me dard, aankhon me dard | eye pain",
    "burning eyes": "आंखों में जलन, aankhon me jalan, aankh me jalan | burning eyes",
    "blurred vision": "धुंधला दिखना, dhundhla dikhna, dhundhla dikhai | blurred vision",
    "rash": "चकत्ते, दाने, chakatte, daane, dane | rash",
    "acidity": "एसिडिटी, खट्टी डकार, khatti dakar | acidity, gas",
    "heartburn": "सीने में जलन, seene me jalan, seene mein jalan | heartburn",
    "constipation": "कब्ज, कब्ज़, kabz, kabj | constipation",
    "chills": "ठंड लगना, कंपकंपी, thand lagna, thand lag rahi, kapkapi | chills",
    "sweating": "पसीना, pasina | sweating",
    "palpitations": "धड़कन तेज, dhadkan tez, dhadkan badh | palpitations",
    "uneasiness": "घबराहट, ghabrahat, ghabrahat hona | uneasiness",
    "weight loss": "वजन कम, wazan kam, wajan kam | weight loss",
    "blood in stool": "मल में खून, potty me khoon, stool me khoon | blood in stool",
    "cramps": "ऐंठन, मरोड़, ainthan, maroda, marod | cramps",
    "sneezing": "छींक, chheenk, chhink, chheenkein | sneezing",
    "numbness": "सुन्न, sunn, sunn pad | numbness",
    "tingling": "झुनझुनी, jhunjhuni | tingling",
    "fainting": "बेहोशी, बेहोश, behoshi, behosh | fainting",
    "muscle pain": "मांसपेशियों में दर्द, maspeshi dard, maspeshiyon me dard | muscle pain",
    "burning sensation": "जलन, jalan | burning sensation",
    "pain": "दर्द, dard | pain, ache",
}
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
    for english, spellings in LEXICON.items():
        hindi, _, eng = spellings.partition("|")
        for group, is_eng in ((hindi, False), (eng, True), (english, True)):
            for s in group.split(","):
                if s.strip():
                    table[tuple(norm(w) for w in s.split())] = (english, is_eng)
    return table


TABLE = _build()
MAX_WORDS = max(map(len, TABLE))
SEVERITY_TABLE = {tuple(norm(w) for w in s.split()) for s in SEVERITY}
SETS = [{norm(w) for w in s} for s in (NUMBERS, UNITS, TIME_WORDS, NEGATION, BREAKS, AFFIRM, FUNCTION_WORDS)]
NUMS, UNITS_N, TIMES, NEGS, BRKS, AFFS, FUNCS = SETS
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
                                "negated": _negated(toks, a, b, text, symptom_idx - own)})
    for a, b, _ in _phrases(words, {k: 1 for k in SEVERITY_TABLE}, used):
        res["severities"].append({"text": text[toks[a][0]:toks[b][1]], "start": toks[a][0], "end": toks[b][1]})
    for key in ("symptoms", "durations", "severities"):
        res[key].sort(key=lambda s: s["start"])
    return res

import pytest
from src.symptoms.hindi import extract, looks_hindi
from src.symptoms.infer import Extractor

# text, symptoms that must be found {english: negated}, durations, severities
CASES = [
    ("mujhe 3 din se bukhar hai, khansi nahi hai", {"fever": False, "cough": True}, ["3 din"], []),
    ("मुझे दो दिन से बुखार है और सिर दर्द नहीं है", {"fever": False, "headache": True}, ["दो दिन"], []),
    ("koi dard nahi, bina bukhar ke", {"pain": True, "fever": True}, [], []),
    ("bukhar hai khansi nahi", {"fever": False, "cough": True}, [], []),
    ("kal raat se bahut tez sar dard hai", {"headache": False}, ["kal raat"], ["bahut tez"]),
    ("mujhe fever hai aur body ache bhi", {"fever": False, "body ache": False}, [], []),
    ("कल से पेट में दर्द है, उल्टी नहीं है", {"stomach pain": False, "vomiting": True}, ["कल"], []),
    ("2 hafte se khujli ho rahi hai", {"itching": False}, ["2 hafte"], []),
    ("teen din se dast aur ulti, bukhar nahi hai", {"loose motions": False, "vomiting": False, "fever": True}, ["teen din"], []),
    ("saans phoolna nahi hai lekin seene me dard hai", {"breathlessness": True, "chest pain": False}, [], []),
    ("peshab me jalan hai thoda sa", {"burning urination": False}, [], ["thoda sa"]),
    ("मुझे ३ दिन से खांसी और जुकाम है", {"cough": False, "cold": False}, ["३ दिन"], []),
    ("bhookh nahi lagti aur neend nahi aati", {"loss of appetite": False, "sleeplessness": False}, [], []),
    ("subah se chakkar aa rahe hain, halka bukhar", {"dizziness": False, "fever": False}, ["subah"], ["halka"]),
    ("bukhaar 5 din se hai, sardi nahin hai", {"fever": False, "cold": True}, ["5 din"], []),
    ("pair me sujan hai, kamzori bhi hai", {"swollen feet": False, "weakness": False}, [], []),
    ("mera sir dard bahut zyada hai 2 ghante se", {"headache": False}, ["2 ghante"], ["bahut zyada"]),
    ("gale me dard hai par khansi nahi", {"sore throat": False, "cough": True}, [], []),
    ("बिना बुखार के कमजोरी है", {"fever": True, "weakness": False}, [], []),
    ("mujhe kal se thakan hai, khujli nahi", {"tiredness": False, "itching": True}, ["kal"], []),
    ("ghutne me dard hai 1 mahine se", {"knee pain": False}, ["1 mahine"], []),
    ("kaan me dard hai tez", {"ear pain": False}, [], ["tez"]),
    ("kabz hai aur pet kharab nahi hai", {"constipation": False, "loose motions": True}, [], []),
    ("mujhe chakkar aur ulti ho rahi hai", {"dizziness": False, "vomiting": False}, [], []),
    ("bhookh nahi lagti, bukhar nahi hai", {"loss of appetite": False, "fever": True}, [], []),
    ("pet saaf nahi hota aur neend nahi aati", {"constipation": False, "sleeplessness": False}, [], []),
    ("मुझे सांस नहीं आती, खांसी नहीं है", {"breathlessness": False, "cough": True}, [], []),
    ("koi peshab nahi aata 2 din se", {"difficulty urinating": False}, ["2 din"], []),
]


@pytest.mark.parametrize("text,symptoms,durations,severities", CASES)
def test_hindi_sentence(text, symptoms, durations, severities):
    assert looks_hindi(text)
    res = extract(text)
    assert {s["english"]: s["negated"] for s in res["symptoms"]} == symptoms
    assert [d["text"] for d in res["durations"]] == durations
    assert [s["text"] for s in res["severities"]] == severities
    for item in res["symptoms"] + res["durations"] + res["severities"]:
        assert text[item["start"]:item["end"]] == item["text"]  # offsets index the original text


@pytest.mark.parametrize("text", ["I have had fever and cough for 3 days, no vomiting",
                                  "Stomach pain since last night, not severe",
                                  "Tell me if the headache gets worse"])
def test_english_not_routed_to_hindi(text):
    assert not looks_hindi(text)


def test_extractor_uses_hindi_rules_for_hindi_text():
    res = Extractor(fallback_to_baseline=True).extract("mujhe 3 din se bukhar hai")
    assert res["extractor_mode"] == "hindi_rules" and res["symptoms"][0]["english"] == "fever"
    assert Extractor(fallback_to_baseline=True).extract("fever for 3 days")["extractor_mode"] == "baseline"


def test_muril_is_opt_in_and_falls_back(monkeypatch):
    ex = Extractor(fallback_to_baseline=True)
    assert ex.extract("mujhe bukhar hai")["extractor_mode"] == "hindi_rules"  # default
    monkeypatch.setenv("CHAKSHU_HINDI_MODEL", "muril")
    res = ex.extract("mujhe 3 din se bukhar hai")
    assert res["extractor_mode"] in ("hindi_muril", "hindi_rules")  # rules if models/muril_hindi_v1 is missing
    assert res["symptoms"][0]["negated"] is False


def test_model_output_keeps_nahi_phrases_positive():
    from src.symptoms.hindi import keep_inside_negation
    model_says = [{"text": "bhookh", "start": 0, "end": 6, "negated": True}, {"text": "bukhar", "start": 19, "end": 25, "negated": True}]
    out = keep_inside_negation("bhookh nahi lagti, bukhar nahi hai", model_says)
    assert [(s["text"], s["negated"]) for s in out] == [("bhookh nahi lagti", False), ("bukhar", True)]

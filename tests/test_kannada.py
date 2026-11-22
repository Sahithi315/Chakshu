import pytest
from src.symptoms.kannada import extract, looks_kannada
from src.symptoms.infer import Extractor

# Early rules, no native-speaker check. text, symptoms {english: negated}, durations, severities
CASES = [
    ("nange 3 dina inda jwara ide, kemmu illa", {"fever": False, "cough": True}, ["3 dina"], []),
    ("ನನಗೆ ಎರಡು ದಿನದಿಂದ ತಲೆ ತುಂಬಾ ನೋವು ಇದೆ, ವಾಂತಿ ಇಲ್ಲ", {"headache": False, "vomiting": True}, ["ಎರಡು ದಿನ"], ["ತುಂಬಾ"]),
    ("ninne inda hotteyalli swalpa novu ide", {"stomach pain": False}, ["ninne"], ["swalpa"]),
    ("jwaravilla aadre kemmu ide", {"fever": True, "cough": False}, [], []),
    ("ಜ್ವರ ಬಂದಿಲ್ಲ, ಕೆಮ್ಮಿಲ್ಲ", {"fever": True, "cough": True}, [], []),
    ("hasivu aagalla, nidde barolla 1 vaara inda", {"loss of appetite": False, "sleeplessness": False}, ["1 vaara"], []),
    ("ಹಸಿವಿಲ್ಲ, ನಿದ್ದೆ ಬರ್ತಾ ಇಲ್ಲ", {"loss of appetite": False, "sleeplessness": False}, [], []),
    ("nange fever ide 2 days inda, cough illa", {"fever": False, "cough": True}, ["2 days"], []),
    ("vaanti aagilla, bhedi ide", {"vomiting": True, "loose motions": False}, [], []),
    ("ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಮತ್ತು ಸುಸ್ತು ಇದೆ", {"fever": False, "tiredness": False}, ["ಮೂರು ದಿನ"], []),
    ("yaavude novu illa", {"pain": True}, [], []),
    ("ede jaasti novu ide monne inda", {"chest pain": False}, ["monne"], ["jaasti"]),
    ("3 dinadinda thale suttu ide", {"dizziness": False}, ["3 dina"], []),
    ("mootradalli uri ide, jwara illa", {"burning urination": False, "fever": True}, [], []),
    ("no jwara, tumba kemmu ide", {"fever": True, "cough": False}, [], ["tumba"]),
    ("ondu vaara inda negadi mattu kemmu ide", {"cold": False, "cough": False}, ["ondu vaara"], []),
    ("ನಿನ್ನೆಯಿಂದ ಮೈ ಕೈ ನೋವು ಮತ್ತು ಜ್ವರ", {"body ache": False, "fever": False}, ["ನಿನ್ನೆ"], []),
    ("kemmu ilva, aadre usiraata tondare ide", {"cough": True, "breathlessness": False}, [], []),
    ("beligge inda tale novu tumba jaasti ide", {"headache": False}, ["beligge"], ["tumba jaasti"]),
    ("೨ ದಿನದಿಂದ ಭೇದಿ ಆಗುತ್ತಿದೆ, ವಾಂತಿ ಆಗಿಲ್ಲ", {"loose motions": False, "vomiting": True}, ["೨ ದಿನ"], []),
    ("nange headache ide, vomiting illa", {"headache": False, "vomiting": True}, [], []),
]


@pytest.mark.parametrize("text,symptoms,durations,severities", CASES)
def test_kannada_sentence(text, symptoms, durations, severities):
    assert looks_kannada(text)
    res = extract(text)
    assert {s["english"]: s["negated"] for s in res["symptoms"]} == symptoms
    assert [d["text"] for d in res["durations"]] == durations
    assert [s["text"] for s in res["severities"]] == severities
    for item in res["symptoms"] + res["durations"] + res["severities"]:
        assert text[item["start"]:item["end"]] == item["text"]  # offsets index the original text


def test_extractor_routes_kannada():
    res = Extractor(fallback_to_baseline=True).extract("nange 3 dina inda jwara ide")
    assert res["extractor_mode"] == "kannada_rules" and res["symptoms"][0]["english"] == "fever"


@pytest.mark.parametrize("text,mode", [
    ("mujhe 3 din se bukhar hai, khansi nahi hai", "hindi_rules"),
    ("मुझे दो दिन से सिर में बहुत दर्द है", "hindi_rules"),
    ("2 din se fever hai aur body pain bhi, bhookh nahi lagti", "hindi_rules"),
    ("I have had a cough for 3 days, no fever", "baseline"),
    ("Tell me if the headache gets worse", "baseline"),
])
def test_hindi_and_english_not_routed_to_kannada(text, mode):
    assert Extractor(fallback_to_baseline=True).extract(text)["extractor_mode"] == mode

# Hindi / Hinglish and Kannada symptom extraction (prototype)

Prototype. Synthetic data only. Not for clinical use.

## What it does
- `Extractor.extract` (`src/symptoms/infer.py`) checks the text with `hindi.looks_hindi`. Devanagari, or Roman-letter Hindi/Hinglish ("mujhe 3 din se bukhar hai"), goes to the Hindi extractor; English text stays on the existing model.
- Output has the same shape and labels as the English path (symptoms with `negated`, durations, severities), plus an `english` name per symptom. The doctor screen shows it in brackets, e.g. "bukhar (fever)".
- Default route, `extractor_mode = hindi_rules`: `src/symptoms/hindi.py`. Lexicon of 117 symptoms in `data/symptoms/hindi/lexicon_review.csv` (Devanagari, Roman and English spellings, `;`-separated; edit the CSV to change it), plus duration, severity and negation-window rules. Phrases with the negation inside the complaint ("bhookh nahi lagti", "neend nahi aati") count as one positive symptom.
- Optional route, `extractor_mode = hindi_muril`: MuRIL (`google/muril-base-cased`) fine-tuned on synthetic data. Off by default. Enable with `CHAKSHU_HINDI_MODEL=muril`; it falls back to the rules if `models/muril_hindi_v1` is missing or fails to load. The same "nahi inside the complaint" post-rule is applied to its output. Weights are not in git.

## Run / demo
```
python run.py                                    # type Hindi text in the intake form
CHAKSHU_HINDI_MODEL=muril python run.py          # optional MuRIL route
python -m pytest tests/test_hindi.py
python -c "from src.symptoms.hindi import extract; print(extract('mujhe 3 din se bukhar hai, khansi nahi hai'))"
```
Demo sentences: "mujhe 3 din se bukhar hai, khansi nahi hai", "मुझे दो दिन से सिर में बहुत दर्द है, उल्टी नहीं", "neend nahi aati ek hafte se".

## Retrain MuRIL
```
python tools/generate_hindi_symptoms.py          # -> data/symptoms/hindi/{all,train,dev}.jsonl (deterministic)
python -m src.symptoms.train --model google/muril-base-cased --data data/symptoms/hindi --out models/muril_hindi_v1 --epochs 12 --bs 16 --dtype fp16
python tools/score_hindi_dev.py models/muril_hindi_v1   # synthetic sanity check, not accuracy
```
About 5 minutes on an RTX 3050 6 GB. WSL has crashed during this run before; close other programs first. The current `models/muril_hindi_v1` was trained before the round-2 lexicon/data update.

## Data
- `train.jsonl` / `dev.jsonl`: synthetic, made by `tools/generate_hindi_symptoms.py` from the lexicon (dev uses unseen patterns and some unseen symptoms).
- `external/*.txt`: Hindi/Hinglish sentences written by other LLMs (ChatGPT, Gemini, Sarvam). Kept as data; not scored.

## Limits
- Rules and training data come from the same hand-written lexicon, and all data is synthetic. Dev scores show that the code runs; they are circular, not accuracy.
- Not tested on real patient text. No accuracy claims for Hindi or Hinglish.
- Spellings outside the lexicon are missed. "aur" ends a negation window ("bukhar aur khansi nahi hai" negates just khansi).
- Severity words may sit inside a lexicon phrase ("सिर में बहुत दर्द", "pet me thoda sa dard", "seene me tez dard"): the full phrase is the symptom and the inner word the severity. Other words inside a phrase ("sir me abhi dard") still split it.
- MuRIL stays opt-in: on demo sentences it split or cut some phrases ("pet me | dard", "chakkar aa") and gives no English name itself (looked up from the lexicon).
- Kannada: see below.

## Kannada (early rules version)
Early rules version, written without a native-speaker check, not tested on real patient text, no accuracy claims.
- `src/symptoms/kannada.py`, `extractor_mode = kannada_rules`. Routed when the text has Kannada script (U+0C80-U+0CFF) or at least 2 Roman-Kannada marker words (nange, ide, illa, inda, tumba, novu, ... or Roman Kannada symptom spellings). If a text looks like both Hindi and Kannada, the one with more marker words wins (ties go to Hindi).
- Lexicon: 51 symptoms in `data/symptoms/kannada/lexicon_review.csv` (Kannada script, Roman, English; column `native_speaker_checked` is "no" for all rows). Same output and `english` label as Hindi, so the doctor screen shows e.g. "jwara (fever)".
- Rules: negation mostly after the symptom (illa, ilva, bandilla, aagilla, fused "jwaravilla", "ಕೆಮ್ಮಿಲ್ಲ"), or "no/not" before; the window stops at commas, aadre/matte/but, "ide" or another symptom. "hasivu aagalla" and "nidde barolla" are complaints, never negated. Durations: number + unit with optional inda (kept outside the span), or ninne/monne/beligge/raatri + inda. Severity words may sit inside body part + novu ("tale tumba novu" = headache). Locative endings are dropped before matching ("hotteyalli" = "hotte").
- Tests: `python -m pytest tests/test_kannada.py` (21 sentences written by the same author as the rules, so they check behaviour, not accuracy).
- Known limits: when "illa" is glued to a word, the span stops at the split point, so "ಕೆಮ್ಮಿಲ್ಲ" shows as "ಕೆಮ್ಮ" and "ದಿನಗಳಿಂದ" as "ದಿನಗಳ". Spellings outside the lexicon and other case endings are missed. "mattu" (and) does not stop negation, but another symptom does, so "jwara mattu kemmu illa" negates just kemmu. No MuRIL model for Kannada.

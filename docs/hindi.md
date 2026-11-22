# Hindi / Hinglish symptom extraction (prototype)

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
- `external/*.txt`: Hindi/Hinglish sentences written by other LLMs (ChatGPT, Gemini, Sarvam). Kept as data only; not scored.

## Limits
- Rules and training data come from the same hand-written lexicon, and all data is synthetic. Dev scores only show the code runs; they are circular, not accuracy.
- Not tested on real patient text. No accuracy claims for Hindi or Hinglish.
- Spellings outside the lexicon are missed. "aur" ends a negation window ("bukhar aur khansi nahi hai" negates only khansi).
- MuRIL stays opt-in: on demo sentences it split or cut some phrases ("pet me | dard", "chakkar aa") and gives no English name itself (looked up from the lexicon).
- Kannada is not done. It would need its own lexicon, script check (U+0C80-0CFF), negation rules ("illa"), generator patterns and real test sentences.

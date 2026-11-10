# Morning summary (Hindi support, overnight run)

## Step 0 (git)
- Started on branch `main`, last commit `e7f55de`, local identical to origin/main, clean tree. No backup branch needed.
- Work is on local branch `multilingual-hindi`. **Local only: you must push it and open the PR yourself.**
- Baseline `pytest` before my changes: 5 failures already present (4 in `test_document_intelligence.py`, 1 in `test_report_pipeline.py::test_filename_sanitization_and_path_traversal`), 53 passed. Not touched by me.
- Installed `pytest` and ran `npm ci` (frontend/node_modules) because both were missing.

## Stage A: rule-based Hindi extractor
- Commit `188c515`. New: `src/symptoms/hindi.py` (lexicon of ~55 symptoms, duration, severity, negation window rules), hooked in `Extractor.extract` (mode `hindi_rules`), `tests/test_hindi.py` (28 tests, all pass). Full suite after: same 5 old failures, 81 passed.
- Frontend: `SummaryCard.jsx` now shows the English name in brackets next to Hindi symptom chips; rebuilt `frontend/dist` (had to run `npm ci` first).
- I also removed one unused `spans = extractor.spans(...)` line in `/api/symptoms/tag` (it ran the model for nothing).
- Known limits of the rules: "aur" ends a negation window (so "bukhar aur khansi nahi hai" only negates khansi); a symptom followed directly by another symptom and then "nahi" is not negated; "pet me thoda sa dard" splits the symptom; unseen words are simply missed.

## Stage B: synthetic data + MuRIL
- `tools/generate_hindi_symptoms.py` -> `data/symptoms/hindi/{all,train,dev}.jsonl`. 1500 rows (600 Roman, 450 Devanagari, 450 English copied from the existing LLM train set), 42 sentence patterns (32 train, 10 dev-only), validated with `load_validated`: 0 bad rows. Dev = 225 Hindi rows with the 10 unseen patterns and 8 symptoms never used in training (tooth pain, hand pain, numbness, tingling, cramps, sneezing, palpitations, burning eyes).
- MuRIL (`google/muril-base-cased`): fast tokenizer with offsets, existing span alignment works unchanged (no code change in train.py/model.py).
- Training: fp16, bs 16, max length 128, lr 5e-5, seed 0. One epoch about 24-34 s; 12 epochs = 268 s. GPU memory not measured.
- DECISION: 5 epochs (as asked) left the model under-trained (it never predicted NEG_SYMPTOM, dev micro F1 0.72). I kept that run as `models/muril_hindi_v1_5ep` and retrained with 12 epochs into `models/muril_hindi_v1` (micro 0.92). I looked at the dev split to decide this, so the dev numbers are mildly tuned. No real test set was involved.
- **Synthetic sanity check, NOT accuracy** (225 synthetic dev messages made from our own lexicon; strict entity F1):

| system | micro | SYMPTOM | NEG_SYMPTOM | DURATION | SEVERITY |
|---|---|---|---|---|---|
| Stage A rules | 0.982 | 0.989 | 0.991 | 0.956 | 0.976 |
| MuRIL 12 epochs | 0.920 | 0.934 | 0.981 | 0.813 | 0.923 |
| MuRIL 5 epochs (under-trained) | 0.720 | 0.773 | 0.000 | 0.879 | 0.766 |

  The rules score high because the generator and the rules share one lexicon (circular). Treat these numbers as "the code runs", nothing more. Typical MuRIL slips: "pehle" glued onto a duration ("3 saal pehle"), words like "shikayat" tagged as symptom.

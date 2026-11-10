# Morning summary (Hindi support, overnight run)

## Step 0 (git)
- Started on branch `main`, last commit `e7f55de`, local identical to origin/main, clean tree. No backup branch needed.
- Work is on local branch `multilingual-hindi`. **Local, not pushed: you must push it and open the PR yourself.**
- Baseline `pytest` before my changes: 5 failures already present (4 in `test_document_intelligence.py`, 1 in `test_report_pipeline.py::test_filename_sanitization_and_path_traversal`), 53 passed. Not touched by me.
- Installed `pytest` and ran `npm ci` (frontend/node_modules) because both were missing.

## Stage A: rule-based Hindi extractor
- Commit `188c515` (Stage B `3c5f6fd`, Stage C `b228c96`). New: `src/symptoms/hindi.py` (lexicon of ~55 symptoms, duration, severity, negation window rules), hooked in `Extractor.extract` (mode `hindi_rules`), `tests/test_hindi.py` (28 tests, all pass). Full suite after: same 5 old failures, 81 passed.
- Frontend: `SummaryCard.jsx` now shows the English name in brackets next to Hindi symptom chips; rebuilt `frontend/dist` (ran `npm ci` beforehand).
- I also removed one unused `spans = extractor.spans(...)` line in `/api/symptoms/tag` (it ran the model for nothing).
- Known limits of the rules: "aur" ends a negation window (so "bukhar aur khansi nahi hai" negates just khansi); a symptom followed directly by another symptom and then "nahi" is not negated; "pet me thoda sa dard" splits the symptom; unseen words are simply missed.

## Stage B: synthetic data + MuRIL
- `tools/generate_hindi_symptoms.py` -> `data/symptoms/hindi/{all,train,dev}.jsonl`. 1500 rows (600 Roman, 450 Devanagari, 450 English copied from the existing LLM train set), 43 sentence patterns (33 train, 10 dev), validated with `load_validated`: 0 bad rows. Dev = 225 Hindi rows with the 10 unseen patterns and 8 symptoms never used in training (tooth pain, hand pain, numbness, tingling, cramps, sneezing, palpitations, burning eyes).
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

## Stage C: use the model?
- Both extractors on 15 demo sentences (GPU; model also runs on CPU, logits checked). Full side-by-side in "Demo sentences" below.
- DECISION: **rules stay the default** for Hindi. MuRIL is wired as an opt-in route (`CHAKSHU_HINDI_MODEL=muril`, mode `hindi_muril`, falls back to rules if `models/muril_hindi_v1` is missing). Reasons: MuRIL flipped negation on "bhookh nahi lagti" / "neend nahi aati" (read as NOT bhookh / NOT neend, a real error), split "pet me | dard", cut "chakkar aa", and gives no English name itself (I look it up from the lexicon). It did handle a few unseen words better (धुंधला दिखता, ghutne me sujan). Net: not clearly "at least as sensible", so I did not switch the default.
- Tests: 82 passed, same 5 old failures.

## Demo sentences (rules | MuRIL; "NOT" = negated, D = duration, V = severity)
| # | sentence | rules | MuRIL |
|---|---|---|---|
| 1 | mujhe 3 din se bukhar hai, khansi nahi hai | bukhar; NOT khansi; D 3 din | same |
| 2 | मुझे दो दिन से बुखार है और सिर दर्द नहीं है | बुखार; NOT सिर दर्द; D दो दिन | same |
| 3 | kal se pet me bahut dard hai aur ulti bhi | dard; ulti; D kal; V bahut | pet me; dard; ulti; D kal; V bahut |
| 4 | bina bukhar ke badan dard ho raha hai | NOT bukhar; badan dard | same |
| 5 | seene me dard nahi hai lekin saans phoolna hai 1 hafte se | NOT seene me dard; saans phoolna; D 1 hafte | same |
| 6 | mujhe fever hai aur thoda sa chakkar aa raha hai | fever; chakkar; V thoda sa | fever; chakkar aa; V thoda sa |
| 7 | पिछले 4 दिन से हल्का सिर दर्द और जुकाम है | सिर दर्द; जुकाम; D 4 दिन; V हल्का | same but D पिछले 4 दिन |
| 8 | peshab me jalan hai, bukhar nahi hai | peshab me jalan; NOT bukhar | same |
| 9 | 2 mahine se kamzori aur bhookh nahi lagti | kamzori; bhookh nahi lagti; D 2 mahine | kamzori; **NOT bhookh**; D 2 mahine |
| 10 | dast aur pet dard ho raha hai subah se, ulti nahi | dast; pet dard; NOT ulti; D subah | same |
| 11 | gale me dard tez hai par khansi nahi | gale me dard; NOT khansi; V tez | same |
| 12 | मेरी आंख में दर्द है और धुंधला दिखता है | आंख में दर्द | आंख में दर्द; धुंधला दिखता |
| 13 | bhai ko nahi, mujhe khujli hai 3 din se | khujli; D 3 din | same (the "bhai ko nahi" part is correctly ignored) |
| 14 | sar dard nahi hai, neend nahi aati kaafi din se | NOT sar dard; neend nahi aati; V kaafi | NOT sar dard; **NOT neend**; D kaafi din |
| 15 | mere ghutne me sujan hai aur jodon me dard bahut zyada | sujan; jodon me dard; V bahut zyada | ghutne me sujan; jodon me dard; V bahut zyada |

Rules miss "धुंधला दिखता" (lexicon has "धुंधला दिखना") and "ghutne" in #15 is missed as a knee symptom.

## How to see it
- Start the app the usual way (`python run.py`), log in, submit an intake or call `/api/symptoms/tag` with Hindi text. Doctor brief chips show e.g. "bukhar (fever)".
- Quick check without the app: `python -c "from src.symptoms.hindi import extract; print(extract('mujhe 3 din se bukhar hai, khansi nahi hai'))"`
- Tests: `python -m pytest tests/test_hindi.py`. Dev check: `python tools/score_hindi_dev.py models/muril_hindi_v1`.

## Decisions I made without you
- 12 epochs instead of 5 for MuRIL (see Stage B). 5-epoch model kept as `models/muril_hindi_v1_5ep`.
- MuRIL is opt-in rather than default (see Stage C).
- Each lexicon entry has one canonical `english` name; "dard" alone maps to "pain", "jalan" to "burning sensation".
- Language check also accepts one function word plus a Hindi-spelled symptom ("bukhar hai"), not just two function words.
- Installed pytest and ran `npm ci`; `frontend/dist` is tracked, so the rebuild shows as changed files in the Stage A commit.
- Did not touch `../Team_404-Vision`, `main`, or anything already in `models/`.

## Left for Kannada
Nothing started. Would need: Kannada lexicon (script + Roman spellings), a language check (Kannada Unicode block U+0C80-0CFF), its own negation rules (Kannada negation is verbal, e.g. "illa"), a generator with Kannada patterns, and a MuRIL run (MuRIL covers Kannada). Real, human-written test sentences are the main missing piece for both languages.

## Reminder
Branch `multilingual-hindi` is local only. Push it and open the PR yourself.

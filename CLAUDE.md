# Clinical Context Platform - Phase 2 demo (Team 404 Vision)

## Goal
Thin demo slice for a college review (possibly 30 Oct 2026). The full product is in `PRD_Clinical_Context_Platform.md`; we build the slice below.

## Scope (in this order)
1. Symptom extraction: patient types symptoms; fine-tuned small encoder tags SYMPTOM, NEG_SYMPTOM, DURATION, SEVERITY.
2. Report extraction: synthetic text-based lab PDFs -> rows (test, value, unit, reference range) with page + word coordinates, via pdfplumber; quote check flags values not found in the source line.
3. UI: one-screen doctor brief; click an item -> source page with line highlighted; Confirm/Correct/Reject per item; plain text box for symptoms.
Out of scope: opening animation, ABDM, HMIS, offline, voice, WhatsApp, handwriting, logins, camera. The watermarked doctor image (`image.png`) stays unused.

## Rules
- Branch `phase2-adit`. Do not push or touch `main` unless Adit says so. Small commits.
- Synthetic data only. No real patient data, ever. Every screen shows: "Prototype. Synthetic data only. Not for clinical use."
- No diagnosis, treatment or medicine advice.
- Wording: UI and docs avoid these words: verified, compliant, certified, "detects errors", "saves time", first, only. Prefer "confirmed", "extracted", "reviewed".
- Short readable code, no needless abstractions. README with exact run commands.
- No credentialed clinical data (MIMIC, n2c2, THYME) or models trained on it (e.g. BioClinical-ModernBERT). No scraped doctor-chat sets (ChatDoctor, MedDialog). CADEC/PsyTAR/TwiMed/DDXPlus: vocabulary/label conventions, never test set, check the licence before use.
- Data format (`data/symptoms/*.json[l]`): `{"text": "...", "spans": [{"start":int,"end":int,"label":"SYMPTOM|DURATION|SEVERITY","negated":bool?}]}`; negated SYMPTOM -> NEG_SYMPTOM internally. Validate and report bad rows; never skip silently.
- Test set: frozen before any training/prompting; different author than train; >=50 negated examples; split by author; near-duplicates removed; never used in generation or tuning.
- Metrics: strict entity-level F1 (exact boundary+type), per-label, 95% bootstrap CI (resample messages), counts beside scores, vs keyword+negation-rule baseline, learning curve at 25/50/100% data. Negation reported separately. Small team-written data overstates real-world performance. No scores from placeholder data. No Hinglish accuracy claims.
- Idea is mostly not new: credibility = honest measured results + visible failure cases.
- Work one stage at a time; stop for Adit's approval after each.

## Environment
WSL Ubuntu, RTX 3050 Laptop 6 GB (30 W cap), Python 3.12, venv at `.venv/`, torch 2.14.1+cu130 (GPU confirmed), transformers 5.21, pdfplumber. Work in the Linux filesystem, not /mnt/c.

## Data (as of 28 Oct night)
- Symptom training data = LLM-generated (`source=llm`), NOT team-written: `TRAIN_SYMPTOMS` (500, author LLM_SYMPTOM_01) + `TRAIN_LLM_01` (5), exported to `data/symptoms/raw/*.csv`. Medication/history/lab/combined sheets are skipped for now.
- Tags other than S/N/D/V (B F M Q U C A E T L P H) are mapped to plain unlabelled text. Body locations ({B}) therefore stay outside the {S} span ("[pain]{S} in [both legs]{B}" -> the word "pain" alone is labelled).
- Known mismatch: the team's calibration GUIDE says to tag the whole expression ("chest hurts", do not tag a body part alone), while the training codebook splits location out. Humans following the guide will likely produce longer spans than the model learned: expect strict-boundary misses.
- The LLM data is very templated (500 messages, 96 tag skeletons, 44 distinct symptom strings, ~30% Hinglish markers). Any LLM-vs-LLM number is not a result.
- Test set: ~40 human-written messages (source=human), due before ~4 pm 29 Oct. Fewer than 50 negated examples is expected: report the count, do not hide it.

## Test-set protocol
1. Train final models on the LLM data with fixed hyperparameters (`train_all`). Done before the test file exists.
2. When the human file arrives: convert -> `prepare --test-author <name> --freeze` (author must not appear in train; near-duplicates removed) -> `eval_all` (each system scored ONCE; `outputs/test_scored.jsonl` blocks re-scoring).
3. Do not retrain or tune after seeing a test score. Report both models (ModernBERT-base = declared main, bert-base-uncased = second row), 3 seeds, the baselines, per-label scores, 95% CIs, counts and failure cases. Small, template-like, team-side data overstates real-world performance. No Hinglish accuracy claims.

## Stage status
- Stage 0: done. Stage 1: done, awaiting final results (needs the human test file). Stage 2: done, awaiting approval.
- Stage 1 contents: converter (plain-text mapping of other tags), validator, `prepare` without a test author, baselines (`baseline_train` = vocabulary from train spans, `baseline` = weaker hand-written list, `baseline_negspacy`), `train_all` (2 models x 25/50/100% x 3 seeds), `eval_all`, `infer.Extractor`. Timing (bs16, len48, 200 steps): ModernBERT bf16 227 ms/step 2.87 GiB, fp16 240 ms 2.88 GiB; bert bf16 147 ms 2.06 GiB, fp16 155 ms 2.06 GiB.
- Stage 2 contents: `src/reports/extract.py` (pdfplumber words/coords, inline and card layouts, quote check, "outside listed range" numeric rule, `highlight()` page renderer via pdfplumber), `src/reports/evaluate.py`. Development layouts classic/compact/cards: 108/108 answer-key rows fully correct. Held-out two_column run once: 36/36. The PDFs come from the team's own generator, so this is not a real-world claim. Caveat: I saw the text of one two_column PDF (report 004) before the held-out rule was given.
- Stage 3 (UI): done, awaiting approval. `app/app.py` (Streamlit). Symptoms: ModernBERT-base `models/modernbert_f100_s1` (fixed in advance). Lab: Stage 2 extractor + `highlight()`. Decisions in `data/decisions.json` (gitignored; original kept, history appended). No scores anywhere in the UI. Run: `streamlit run app/app.py`.
- Stage 4: not started.
- Push: not allowed for now (and no GitHub credentials in WSL).

## Run
```
source .venv/bin/activate
pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"
```
Symptom pipeline commands: see README.md.

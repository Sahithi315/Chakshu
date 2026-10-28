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
- No credentialed clinical data (MIMIC, n2c2, THYME) or models trained on it (e.g. BioClinical-ModernBERT). No scraped doctor-chat sets (ChatDoctor, MedDialog). CADEC/PsyTAR/TwiMed/DDXPlus: vocabulary/label conventions only, never test set, check the licence before use.
- Data format (`data/symptoms/*.json[l]`): `{"text": "...", "spans": [{"start":int,"end":int,"label":"SYMPTOM|DURATION|SEVERITY","negated":bool?}]}`; negated SYMPTOM -> NEG_SYMPTOM internally. Validate and report bad rows; never skip silently.
- Test set: frozen before any training/prompting; different author than train; >=50 negated examples; split by author; near-duplicates removed; never used in generation or tuning.
- Metrics: strict entity-level F1 (exact boundary+type), per-label, 95% bootstrap CI (resample messages), counts beside scores, vs keyword+negation-rule baseline, learning curve at 25/50/100% data. Negation reported separately. Small team-written data overstates real-world performance. No scores from placeholder data. No Hinglish accuracy claims.
- Idea is mostly not new: credibility = honest measured results + visible failure cases.
- Work one stage at a time; stop for Adit's approval after each.

## Environment
WSL Ubuntu, RTX 3050 Laptop 6 GB (30 W cap), Python 3.12, venv at `.venv/`, torch 2.14.1+cu130 (GPU confirmed), transformers 5.21, pdfplumber. Work in the Linux filesystem, not /mnt/c.

## Stage status
- Stage 0: done and approved.
- Stage 1: code done, awaiting approval. Pipeline ran end to end on the 50-line placeholder (`data/placeholder/`, assistant-written, NOT team data; scores hidden). No real scores exist yet.
  - Timing (bs16, len48, 200 steps): ModernBERT-base bf16 227 ms/step 2.87 GiB, fp16 240 ms/step 2.88 GiB; bert-base-uncased bf16 147 ms/step 2.06 GiB, fp16 155 ms/step 2.06 GiB. No NaN losses.
  - TODO when team data arrives: convert -> prepare (--test-author) -> freeze -> baseline eval -> curve -> final train -> evaluate. Warn Adit if test < 100 messages or < 50 with negation.
- Stage 2-4: not started.

## Run
```
source .venv/bin/activate
pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"
```
Symptom pipeline commands: see README.md.

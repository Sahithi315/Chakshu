# Clinical Context Platform: Phase 2 demo

Prototype. Synthetic data only. Not for clinical use.

## Setup
```
python3 -m venv .venv && source .venv/bin/activate
pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"   # must print True
```

## Doctor screen (Stage 3)
```
source .venv/bin/activate
streamlit run app/app.py        # opens http://localhost:8501
```
Needs `models/modernbert_f100_s1` (made by `train_all`). Symptom tags come from ModernBERT-base (100% data, seed 1, declared in advance); lab rows come from the Stage 2 extractor. Confirm / Correct / Reject are saved to `data/decisions.json` (local, not committed); a correction keeps the original value. The screen shows no scores.

## Report extractor (Stage 2)
```
python -m src.reports.evaluate               # development layouts vs the answer key (classic, compact, cards)
python -m src.reports.evaluate --held-out    # two_column, run once
python -c "from src.reports.extract import extract_pdf, highlight; r = extract_pdf('data/synthetic_lab_reports/synthetic_report_002.pdf'); highlight('data/synthetic_lab_reports/synthetic_report_002.pdf', r[3]['page'], r[3]['bbox']).save('outputs/demo.png')"
```
Each row: test, value, unit, reference_range, page, bbox, source_line, quote_ok, range_note ("outside listed range" or empty). The PDFs come from the team's own generator; accuracy here is not a real-world claim.

## Symptom pipeline (Stage 1)
Team data: CSV with columns `id, author, text_marked, source`; tags `[phrase]{S|N|D|V}` (S symptom, N denied symptom, D duration, V severity). Tag the phrase only, not "no"/"denies".
```
# 1. CSV -> JSONL (lists malformed rows, exit code 1 if any; tags other than S/N/D/V become plain text)
python -m src.symptoms.convert data/symptoms/raw/*.csv --out data/symptoms/all.jsonl
# 2a. train-only (no test set yet)
python -m src.symptoms.prepare --inp data/symptoms/all.jsonl --out data/symptoms/split
# 2b. when the human test file exists: add its CSV to step 1, then split by author and freeze
python -m src.symptoms.prepare --inp data/symptoms/all.jsonl --out data/symptoms/split --test-author TESTAUTHOR --freeze
# 3. timing and memory test (200 steps, bf16 vs fp16)
python -m src.symptoms.timing --model answerdotai/ModernBERT-base
# 4. baseline (keyword list + negation rule; add _negspacy for the negspaCy variant)
python -m src.symptoms.evaluate --system baseline_train --data data/symptoms/split   # also: baseline, baseline_negspacy
# 5. train everything once (ModernBERT-base and bert-base-uncased x 25/50/100% x 3 seeds), then score once each
python -m src.symptoms.train_all --data data/symptoms/split
python -m src.symptoms.eval_all --data data/symptoms/split
# 6. use it
python -c "from src.symptoms.infer import Extractor; print(Extractor('models/modernbert_f100_s0').extract('no fever but cough for 3 days'))"
```
Placeholder data (50 lines written by the assistant, not team data; scores hidden) lives in `data/placeholder/`.

Test-set rules: written by one human author who writes no training data, frozen (hash stored), scored once per system, never used for tuning. Small team-written data overstates real-world performance.

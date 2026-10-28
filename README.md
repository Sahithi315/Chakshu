# Clinical Context Platform: Phase 2 demo

Prototype. Synthetic data only. Not for clinical use.

## Setup
```
python3 -m venv .venv && source .venv/bin/activate
pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"   # must print True
```

## Symptom pipeline (Stage 1)
Team data: CSV with columns `id, author, text_marked, source`; tags `[phrase]{S|N|D|V}` (S symptom, N denied symptom, D duration, V severity). Tag the phrase only, not "no"/"denies".
```
# 1. CSV -> JSONL (lists malformed rows, exit code 1 if any)
python -m src.symptoms.convert data/symptoms/raw/*.csv --out data/symptoms/all.jsonl
# 2. validate, split by author, drop near-duplicates, freeze the test set
python -m src.symptoms.prepare --inp data/symptoms/all.jsonl --out data/symptoms/split --test-author TESTAUTHOR --freeze
# 3. timing and memory test (200 steps, bf16 vs fp16)
python -m src.symptoms.timing --model answerdotai/ModernBERT-base
# 4. baseline (keyword list + negation rule; add _negspacy for the negspaCy variant)
python -m src.symptoms.evaluate --system baseline --data data/symptoms/split
# 5. train and evaluate (25/50/100% learning curve; final model uses the 100% run)
python -m src.symptoms.curve --model answerdotai/ModernBERT-base --data data/symptoms/split
python -m src.symptoms.train --model answerdotai/ModernBERT-base --data data/symptoms/split --out models/final
python -m src.symptoms.evaluate --system models/final --data data/symptoms/split
# 6. use it
python -c "from src.symptoms.infer import Extractor; print(Extractor('models/final').extract('no fever but cough for 3 days'))"
```
Placeholder pipeline test (50 lines written by the assistant, not team data; scores are hidden):
`data/placeholder/` uses the same commands with `--data data/placeholder/split`.

Test-set rules: written by one author who writes no training data, frozen before training (hash stored), never used for tuning. Small team-written data overstates real-world performance.

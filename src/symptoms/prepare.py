"""Validate, split by author, de-duplicate and (optionally) freeze the test set.

python -m src.symptoms.prepare --inp data/symptoms/all.jsonl --out data/symptoms/split --test-author NAME [--freeze]
"""
import argparse, json, os, sys
from .data import load_validated, split_by_author, summary, freeze_test


def dump(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--test-author", nargs="+", default=None)  # omit: train-only, no test set yet
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    rows, errors = load_validated(a.inp)
    for e in errors:
        print("ERROR", e)
    if errors:
        sys.exit(f"STOP: {len(errors)} malformed rows. Fix them; nothing was skipped silently.")
    os.makedirs(a.out, exist_ok=True)
    if not a.test_author:
        dump(rows, f"{a.out}/train.jsonl")
        print("train-only:", summary(rows)); return
    train, test, dropped = split_by_author(rows, a.test_author)
    dump(train, f"{a.out}/train.jsonl"); dump(test, f"{a.out}/test.jsonl")
    dump(dropped, f"{a.out}/dropped_near_duplicates.jsonl")
    print("train:", summary(train)); print("test: ", summary(test))
    print(f"near-duplicates removed from train: {len(dropped)}")
    st = summary(test)
    if st["messages"] < 100:
        print(f"WARNING: test set has {st['messages']} messages (target 120, floor 100).")
    if st["with_negated"] < 50:
        print(f"WARNING: only {st['with_negated']} test messages contain a negated symptom (need >= 50).")
    if a.freeze:
        freeze_test(test, a.test_author, f"{a.out}/test_freeze.json")
        print("test set frozen (sha256 recorded).")


if __name__ == "__main__":
    main()

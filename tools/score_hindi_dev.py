"""Synthetic sanity check on the Hindi dev split (NOT accuracy): python tools/score_hindi_dev.py [model_dir]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.symptoms import hindi
from src.symptoms.evaluate import evaluate, failures
from src.symptoms.infer import Extractor, structure

rows = [json.loads(l) for l in open("data/symptoms/hindi/dev.jsonl", encoding="utf-8")]
texts = [r["text"] for r in rows]


def rules(t):
    res = hindi.extract(t)
    return ([{"start": s["start"], "end": s["end"], "label": "NEG_SYMPTOM" if s["negated"] else "SYMPTOM"} for s in res["symptoms"]]
            + [{**d, "label": "DURATION"} for d in res["durations"]] + [{**d, "label": "SEVERITY"} for d in res["severities"]])


systems = {"hindi_rules": [rules(t) for t in texts]}
if len(sys.argv) > 1:
    systems[sys.argv[1]] = Extractor(sys.argv[1]).spans(texts)
for name, preds in systems.items():
    res = evaluate(rows, preds, n_boot=200)
    print(f"\n== {name} on {len(rows)} synthetic dev messages (synthetic sanity check, not accuracy)")
    for k, e in res["scores"].items():
        print(f"  {k:24s}{e['value']:.3f}  CI [{e['ci95'][0]:.3f}, {e['ci95'][1]:.3f}]" + (f"  tp={e['tp']} fp={e['fp']} fn={e['fn']}" if "tp" in e else ""))
    print(f"  negation polarity right: {res['negation_polarity_right']}/{res['negation_boundaries_found']}")
    for f in failures(rows, preds, 4):
        print("   miss:", f["text"], f["missed"], "spurious:", f["spurious"])

"""Learning curve: train on 25/50/100% of the training messages, evaluate each on the frozen test set.
python -m src.symptoms.curve --model answerdotai/ModernBERT-base --data data/symptoms/split"""
import argparse, json, os
from .evaluate import evaluate, predictor, print_report
from .train import train

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True); ap.add_argument("--data", required=True)
ap.add_argument("--seeds", type=int, nargs="+", default=[0]); ap.add_argument("--epochs", type=int, default=10)
a = ap.parse_args()
test = [json.loads(l) for l in open(f"{a.data}/test.jsonl", encoding="utf-8")]
placeholder = "placeholder" in a.data.lower()
curve = []
for frac in (0.25, 0.5, 1.0):
    for seed in a.seeds:
        out = f"models/curve_{int(frac*100)}_s{seed}"
        n = train(a.model, a.data, frac, out, epochs=a.epochs, seed=seed)
        res = evaluate(test, predictor(out)([r["text"] for r in test]))
        print_report(f"{a.model} frac={frac} seed={seed} n_train={n}", res, placeholder)
        curve.append({"frac": frac, "seed": seed, "n_train": n, "result": res})
if not placeholder:
    os.makedirs("outputs", exist_ok=True)
    json.dump(curve, open("outputs/learning_curve.json", "w"), indent=1)

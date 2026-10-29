"""Train every planned model once: {ModernBERT-base (main), bert-base-uncased} x {25,50,100%} x 3 seeds.
Fixed hyperparameters, no dev split. Nothing here reads a test set.
python -m src.symptoms.train_all --data data/symptoms/split"""
import argparse, os
from .train import train

MODELS = {"modernbert": "answerdotai/ModernBERT-base", "bert": "google-bert/bert-base-uncased"}
ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True); ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
a = ap.parse_args()
for short, name in MODELS.items():
    for frac in (0.25, 0.5, 1.0):
        for seed in a.seeds:
            out = f"models/{short}_f{int(frac*100)}_s{seed}"
            if os.path.exists(f"{out}/train_info.json"):
                continue
            print(f"--- {out}", flush=True); train(name, a.data, frac, out, seed=seed)

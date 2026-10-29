"""Score every trained model and the baselines on the frozen test set, once each, and write one table.
python -m src.symptoms.eval_all --data data/symptoms/split"""
import argparse, glob, json, os, subprocess, sys

ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); a = ap.parse_args()
systems = ["baseline_train", "baseline", "baseline_negspacy"] + sorted(glob.glob("models/*_f*_s*"))
for s in systems:
    r = subprocess.run([sys.executable, "-m", "src.symptoms.evaluate", "--system", s, "--data", a.data], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip().splitlines()[-1])
res = {os.path.basename(f)[5:-5]: json.load(open(f))["result"]["scores"] for f in glob.glob("outputs/eval_*.json")}
print("\nmicro F1 by system:")
for k, v in sorted(res.items()):
    print(f"  {k:24s}{v['micro']['value']:.3f}  CI [{v['micro']['ci95'][0]:.3f}, {v['micro']['ci95'][1]:.3f}]  NEG_SYMPTOM {v['NEG_SYMPTOM']['value']:.3f}")

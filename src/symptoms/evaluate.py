"""Strict entity-level evaluation (exact boundaries + type) with 95% bootstrap CIs over messages.

python -m src.symptoms.evaluate --system baseline|baseline_negspacy|models/NAME --data data/symptoms/split
"""
import argparse, json, os
import numpy as np
from .data import LABELS, check_frozen, sha


def counts(gold, pred):
    """Per-label [tp, fp, fn] for one message, strict match on (start, end, label)."""
    g = {(s["start"], s["end"], s["label"]) for s in gold}
    p = {(s["start"], s["end"], s["label"]) for s in pred}
    return [[len({x for x in g & p if x[2] == l}), len({x for x in p - g if x[2] == l}), len({x for x in g - p if x[2] == l})]
            for l in LABELS]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0), p, r


def negation_stats(gold, pred):
    """Negation, separate from span F1: among gold symptoms whose boundaries were found (either polarity),
    how often was the polarity right?  Returns [boundary_found, polarity_right]."""
    pp = {(s["start"], s["end"]): s["label"] for s in pred if s["label"] in ("SYMPTOM", "NEG_SYMPTOM")}
    found = right = 0
    for s in gold:
        if s["label"] in ("SYMPTOM", "NEG_SYMPTOM") and (s["start"], s["end"]) in pp:
            found += 1; right += pp[(s["start"], s["end"])] == s["label"]
    return [found, right]


def evaluate(rows, preds, n_boot=1000, seed=0):
    C = np.array([counts(r["spans"], p) for r, p in zip(rows, preds)])      # [msg, label, 3]
    N = np.array([negation_stats(r["spans"], p) for r, p in zip(rows, preds)])  # [msg, 2]
    rng = np.random.default_rng(seed)
    def scores(idx):
        c = C[idx].sum(0); n = N[idx].sum(0)
        d = {"micro": prf(*c.sum(0))[0], **{l: prf(*c[i])[0] for i, l in enumerate(LABELS)},
             "negation_polarity_acc": n[1] / n[0] if n[0] else float("nan")}
        return d
    point = scores(np.arange(len(rows)))
    boots = [scores(rng.integers(0, len(rows), len(rows))) for _ in range(n_boot)]
    total = C.sum(0); n = N.sum(0)
    out = {"n_messages": len(rows), "negation_boundaries_found": int(n[0]), "negation_polarity_right": int(n[1]), "scores": {}}
    for k in point:
        v = np.array([b[k] for b in boots]); ok = ~np.isnan(v)
        lo, hi = np.percentile(v[ok], [2.5, 97.5]) if ok.any() else (float("nan"),) * 2
        entry = {"value": point[k], "ci95": [float(lo), float(hi)]}
        if k in LABELS:
            tp, fp, fn = total[LABELS.index(k)]; entry.update(tp=int(tp), fp=int(fp), fn=int(fn), gold=int(tp + fn))
        elif k == "micro":
            tp, fp, fn = total.sum(0); entry.update(tp=int(tp), fp=int(fp), fn=int(fn), gold=int(tp + fn))
        out["scores"][k] = entry
    return out


def failures(rows, preds, limit=40):
    out = []
    for r, p in zip(rows, preds):
        g = {(s["start"], s["end"], s["label"]) for s in r["spans"]}; q = {(s["start"], s["end"], s["label"]) for s in p}
        if g != q:
            t = r["text"]
            show = lambda x: [(t[a:b], l) for a, b, l in sorted(x)]
            out.append({"id": r["id"], "text": t, "missed": show(g - q), "spurious": show(q - g)})
    return out[:limit]


def predictor(system, data=None):
    if system == "baseline_train":
        from . import baseline; f = baseline.from_train(f"{data}/train.jsonl"); return lambda texts: [f(t) for t in texts]
    if system == "baseline":
        from . import baseline; return lambda texts: [baseline.predict(t) for t in texts]
    if system == "baseline_negspacy":
        from . import baseline; return lambda texts: [baseline.predict_negspacy(t) for t in texts]
    from .infer import Extractor; return Extractor(system).spans


def print_report(name, res, placeholder):
    print(f"\n== {name}  (n={res['n_messages']} messages)")
    if placeholder:
        print("PLACEHOLDER DATA: pipeline ran end to end. Scores and counts are hidden on purpose.")
        return
    for k, e in res["scores"].items():
        cnt = f"tp={e['tp']} fp={e['fp']} fn={e['fn']} gold={e['gold']}" if "tp" in e else ""
        print(f"  {k:24s}{e['value']:.3f}  95% CI [{e['ci95'][0]:.3f}, {e['ci95'][1]:.3f}]   {cnt}")
    print(f"  negation: polarity right on {res['negation_polarity_right']} of {res['negation_boundaries_found']} gold symptoms whose boundaries were found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True); ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    test = [json.loads(l) for l in open(f"{a.data}/test.jsonl", encoding="utf-8")]
    check_frozen(test, f"{a.data}/test_freeze.json")
    placeholder = "placeholder" in a.data.lower()
    if not placeholder:  # each system is scored on the real test set once; no re-scoring after seeing a number
        log = "outputs/test_scored.jsonl"; key = {"system": a.system, "test_sha": sha(test)}
        if os.path.exists(log) and any(json.loads(l) == key for l in open(log)):
            raise SystemExit(f"STOP: {a.system} was already scored on this test set. Not re-scoring.")
        os.makedirs("outputs", exist_ok=True); open(log, "a").write(json.dumps(key) + "\n")
    preds = predictor(a.system, a.data)([r["text"] for r in test])
    res = evaluate(test, preds)
    print_report(a.system, res, placeholder)
    if not placeholder:
        os.makedirs("outputs", exist_ok=True)
        tag = os.path.basename(a.system.rstrip("/"))
        json.dump({"system": a.system, "result": res, "failures": failures(test, preds)}, open(a.out or f"outputs/eval_{tag}.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()

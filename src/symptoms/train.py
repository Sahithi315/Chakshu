"""Fine-tune a token-classification model. Fixed hyperparameters, no model selection on the test set.

python -m src.symptoms.train --model answerdotai/ModernBERT-base --data data/symptoms/split --frac 1.0 --out models/final
"""
import argparse, json, random, time
import torch
from .model import load, encode, collate


def train(model_name, data_dir, frac, out, epochs=10, bs=16, lr=5e-5, seed=0, dtype="bf16"):
    # training only reads train.jsonl; the test set does not exist yet (or is not touched) at this point
    rows = [json.loads(l) for l in open(f"{data_dir}/train.jsonl", encoding="utf-8")]
    random.Random(seed).shuffle(rows)
    rows = rows[:max(1, round(len(rows) * frac))]
    torch.manual_seed(seed)
    tok, model = load(model_name)
    model.cuda().train()
    data = [encode(tok, r)[0] for r in rows]
    steps = epochs * ((len(data) + bs - 1) // bs)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / max(1, steps // 10), (steps - s) / max(1, steps - steps // 10)))
    amp = torch.bfloat16 if dtype == "bf16" else torch.float16
    scaler = torch.amp.GradScaler(enabled=dtype == "fp16")
    t0, step = time.time(), 0
    for ep in range(epochs):
        random.Random(seed + ep).shuffle(data)
        for i in range(0, len(data), bs):
            batch = {k: v.cuda() for k, v in collate(data[i:i + bs], tok.pad_token_id).items()}
            with torch.autocast("cuda", dtype=amp):
                loss = model(**batch).loss
            scaler.scale(loss).backward(); scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True); sched.step(); step += 1
        if ep % 3 == 0 or ep == epochs - 1:
            print(f"epoch {ep+1}/{epochs} loss {loss.item():.4f} ({time.time()-t0:.0f}s)")
    model.save_pretrained(out); tok.save_pretrained(out)
    json.dump({"base": model_name, "n_train": len(rows), "frac": frac, "epochs": epochs, "bs": bs, "lr": lr, "seed": seed, "dtype": dtype},
              open(f"{out}/train_info.json", "w"))
    return len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--frac", type=float, default=1.0); ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--bs", type=int, default=16); ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp16"])
    a = ap.parse_args()
    train(a.model, a.data, a.frac, a.out, a.epochs, a.bs, a.lr, a.seed, a.dtype)

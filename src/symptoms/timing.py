"""200-step timing and peak-VRAM test, bf16 vs fp16 autocast (fp32 master weights).
python -m src.symptoms.timing --model answerdotai/ModernBERT-base
Uses random token ids of a realistic length: this measures speed and memory, not accuracy."""
import argparse, time, torch
from .model import load, TAGS


def run(model_name, dtype, bs, seqlen, steps=200):
    tok, model = load(model_name)
    model.cuda().train()
    opt = torch.optim.AdamW(model.parameters(), lr=3e-5)
    scaler = torch.amp.GradScaler(enabled=dtype == torch.float16)
    ids = torch.randint(1000, 5000, (bs, seqlen), device="cuda")
    labels = torch.randint(0, len(TAGS), (bs, seqlen), device="cuda")
    torch.cuda.reset_peak_memory_stats()
    losses = []
    for i in range(steps):
        if i == 10:  # skip warm-up
            torch.cuda.synchronize(); t0 = time.time()
        with torch.autocast("cuda", dtype=dtype):
            loss = model(input_ids=ids, labels=labels).loss
        scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
        losses.append(loss.item())
    torch.cuda.synchronize()
    dt = (time.time() - t0) / (steps - 10)
    nan = any(l != l for l in losses)
    print(f"{model_name} {str(dtype).split('.')[-1]:9s} bs={bs} len={seqlen}: {dt*1000:.0f} ms/step, "
          f"peak {torch.cuda.max_memory_allocated()/2**30:.2f} GiB, nan_loss={nan}")
    del model, opt; torch.cuda.empty_cache()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--bs", type=int, default=16); ap.add_argument("--len", type=int, default=48)
    a = ap.parse_args()
    for dt in (torch.bfloat16, torch.float16):
        run(a.model, dt, a.bs, a.len)

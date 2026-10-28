"""Inference: text -> structured symptoms with character spans.

    from src.symptoms.infer import Extractor
    Extractor("models/final").extract("no fever but cough for 3 days")
"""
import torch
from .model import load, encode, decode, collate


class Extractor:
    def __init__(self, model_dir):
        self.tok, self.model = load(model_dir)
        self.model.eval().to("cuda" if torch.cuda.is_available() else "cpu")

    @torch.no_grad()
    def spans(self, texts):
        """Raw predicted spans [{start,end,label}] for each text."""
        out = []
        for i in range(0, len(texts), 32):
            chunk = [encode(self.tok, {"text": t}, with_labels=False) for t in texts[i:i + 32]]
            batch = collate([c[0] for c in chunk], self.tok.pad_token_id)
            logits = self.model(**{k: v.to(self.model.device) for k, v in batch.items()}).logits
            for (enc, offs), t, pred in zip(chunk, texts[i:i + 32], logits.argmax(-1).tolist()):
                out.append(decode(t, offs, pred[:len(offs)]))
        return out

    def extract(self, text):
        return structure(text, self.spans([text])[0])


def structure(text, spans):
    """Group raw spans into the structured form the UI uses."""
    res = {"text": text, "symptoms": [], "durations": [], "severities": []}
    for s in spans:
        item = {"text": text[s["start"]:s["end"]], "start": s["start"], "end": s["end"]}
        if s["label"] in ("SYMPTOM", "NEG_SYMPTOM"):
            res["symptoms"].append({**item, "negated": s["label"] == "NEG_SYMPTOM"})
        elif s["label"] == "DURATION":
            res["durations"].append(item)
        else:
            res["severities"].append(item)
    return res

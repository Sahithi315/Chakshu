"""Inference: text -> structured symptoms with character spans.

    from src.symptoms.infer import Extractor
    Extractor("models/modernbert_f100_s1").extract("no fever but cough for 3 days")
"""
from pathlib import Path
import os
import torch
from .model import load, encode, decode, collate, ModelNotFoundError, ModelLoadError
from .baseline import predict, from_train


class Extractor:
    """Symptom extractor supporting both fine-tuned transformer models and rule-based fallback."""

    def __init__(self, model_dir=None, fallback_to_baseline=False, train_data_path=None):
        self.model_dir = model_dir
        self.fallback_to_baseline = fallback_to_baseline
        self.mode = "model"
        self.tok = None
        self.model = None
        self._baseline_fn = None

        if model_dir:
            try:
                self.tok, self.model = load(model_dir)
                self.model.eval().to("cuda" if torch.cuda.is_available() else "cpu")
                self.mode = "model"
            except (ModelNotFoundError, ModelLoadError) as e:
                if not fallback_to_baseline:
                    raise
                # Graceful honest fallback to baseline
                self.mode = "baseline"
                self._init_baseline(train_data_path)
            except Exception as e:
                if not fallback_to_baseline:
                    raise ModelLoadError(f"Unexpected error loading model from {model_dir}: {e}") from e
                self.mode = "baseline"
                self._init_baseline(train_data_path)
        else:
            if not fallback_to_baseline:
                raise ValueError("Either model_dir or fallback_to_baseline=True must be specified.")
            self.mode = "baseline"
            self._init_baseline(train_data_path)

    def _init_baseline(self, train_data_path=None):
        """Initialize the rule-based baseline predictor."""
        if train_data_path and Path(train_data_path).exists():
            self._baseline_fn = from_train(str(train_data_path))
        else:
            # Check default project train data locations
            default_train = Path(__file__).resolve().parent.parent.parent / "data" / "symptoms" / "split" / "train.jsonl"
            if default_train.exists():
                self._baseline_fn = from_train(str(default_train))
            else:
                self._baseline_fn = predict

    @torch.no_grad()
    def spans(self, texts):
        """Raw predicted spans [{start,end,label}] for each text."""
        if self.mode == "baseline":
            return [self._baseline_fn(t) for t in texts]

        out = []
        for i in range(0, len(texts), 32):
            chunk = [encode(self.tok, {"text": t}, with_labels=False) for t in texts[i:i + 32]]
            batch = collate([c[0] for c in chunk], self.tok.pad_token_id)
            logits = self.model(**{k: v.to(self.model.device) for k, v in batch.items()}).logits
            for (enc, offs), t, pred in zip(chunk, texts[i:i + 32], logits.argmax(-1).tolist()):
                out.append(decode(t, offs, pred[:len(offs)]))
        return out

    def extract(self, text):
        res = structure(text, self.spans([text])[0])
        res["extractor_mode"] = self.mode
        return res


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

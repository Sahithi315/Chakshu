"""Shared token-classification helpers: BIO encoding of char spans and decoding back to char spans."""
from pathlib import Path
import os
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer
from .data import LABELS

TAGS = ["O"] + [f"{p}-{l}" for l in LABELS for p in "BI"]
T2I = {t: i for i, t in enumerate(TAGS)}
MAXLEN = 128


class ModelNotFoundError(FileNotFoundError):
    """Raised when a local model checkpoint directory does not exist."""
    pass


class ModelLoadError(RuntimeError):
    """Raised when a model checkpoint directory is invalid, corrupt, or missing required files."""
    pass


def is_local_path(name_or_dir):
    """Check whether name_or_dir is intended to be a local filesystem path."""
    p = Path(name_or_dir)
    if p.exists():
        return True
    p_str = str(name_or_dir)
    # Check for explicit filesystem path indicators
    if (
        os.path.isabs(p_str)
        or "\\" in p_str
        or p_str.startswith((".", "~"))
        or p_str.startswith("models/")
        or p_str.startswith("models\\")
    ):
        return True
    return False


def validate_local_model_dir(path):
    """Verify that a local model directory exists and has the required files."""
    p = Path(path).resolve()
    if not p.exists():
        raise ModelNotFoundError(
            f"Model directory not found at: {p}\n"
            f"Expected a fine-tuned model checkpoint directory.\n"
            f"Setup instructions: train the planned model using:\n"
            f"  python -m src.symptoms.train_all --data data/symptoms/split"
        )
    if not p.is_dir():
        raise ModelLoadError(f"Model path exists but is not a directory: {p}")

    # Check for essential configuration and weight files
    has_config = (p / "config.json").is_file()
    has_weights = any((p / f).is_file() for f in ("model.safetensors", "pytorch_model.bin")) or list(p.glob("*.safetensors"))
    has_tokenizer = any((p / f).is_file() for f in ("tokenizer_config.json", "vocab.txt", "tokenizer.json", "spiece.model"))

    missing = []
    if not has_config:
        missing.append("config.json")
    if not has_weights:
        missing.append("model.safetensors or pytorch_model.bin")
    if not has_tokenizer:
        missing.append("tokenizer_config.json or tokenizer.json or vocab.txt")

    if missing:
        raise ModelLoadError(
            f"Model checkpoint directory at '{p}' is incomplete or malformed.\n"
            f"Missing required file(s): {', '.join(missing)}.\n"
            f"Setup instructions: run training or verify checkpoint export:\n"
            f"  python -m src.symptoms.train_all --data data/symptoms/split"
        )
    return p


def load(name_or_dir):
    """Load tokenizer and model with robust local path handling and clear error states."""
    if is_local_path(name_or_dir):
        resolved = validate_local_model_dir(name_or_dir)
        try:
            tok = AutoTokenizer.from_pretrained(str(resolved), local_files_only=True)
            model = AutoModelForTokenClassification.from_pretrained(
                str(resolved),
                num_labels=len(TAGS),
                id2label=dict(enumerate(TAGS)),
                label2id=T2I,
                local_files_only=True
            )
            return tok, model
        except Exception as e:
            if isinstance(e, (ModelNotFoundError, ModelLoadError)):
                raise
            raise ModelLoadError(f"Failed to load model from local directory '{resolved}': {e}") from e
    else:
        # Remote model ID on Hugging Face Hub (requires network access)
        try:
            tok = AutoTokenizer.from_pretrained(name_or_dir)
            model = AutoModelForTokenClassification.from_pretrained(
                name_or_dir, num_labels=len(TAGS), id2label=dict(enumerate(TAGS)), label2id=T2I
            )
            return tok, model
        except Exception as e:
            raise ModelLoadError(f"Failed to load remote model '{name_or_dir}': {e}") from e


def encode(tok, row, with_labels=True):
    enc = tok(row["text"], return_offsets_mapping=True, truncation=True, max_length=MAXLEN)
    offs = enc.pop("offset_mapping")
    if with_labels:
        labels = []
        for s, e in offs:
            tag = "O"
            if e > s:
                for sp in row["spans"]:
                    if s < sp["end"] and e > sp["start"]:  # token overlaps span
                        tag = ("B-" if s <= sp["start"] else "I-") + sp["label"]
                        break
            labels.append(T2I[tag] if e > s else -100)  # special tokens ignored
        enc["labels"] = labels
    return enc, offs


def decode(text, offs, tag_ids):
    """Merge B-/I- tags into char spans [{start,end,label}], trimmed of whitespace."""
    spans, cur = [], None
    for (s, e), t in zip(offs, tag_ids):
        tag = TAGS[t] if e > s else "O"
        if tag == "O":
            cur = None
            continue
        p, lab = tag.split("-", 1)
        if p == "B" or cur is None or cur["label"] != lab:
            cur = {"start": s, "end": e, "label": lab}; spans.append(cur)
        else:
            cur["end"] = e
    for sp in spans:
        seg = text[sp["start"]:sp["end"]]
        sp["start"] += len(seg) - len(seg.lstrip()); sp["end"] -= len(seg) - len(seg.rstrip())
    return spans


def collate(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    ids = torch.tensor([b["input_ids"] + [pad_id] * (n - len(b["input_ids"])) for b in batch])
    att = torch.tensor([[1] * len(b["input_ids"]) + [0] * (n - len(b["input_ids"])) for b in batch])
    out = {"input_ids": ids, "attention_mask": att}
    if "labels" in batch[0]:
        out["labels"] = torch.tensor([b["labels"] + [-100] * (n - len(b["labels"])) for b in batch])
    return out

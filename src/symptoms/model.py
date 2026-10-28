"""Shared token-classification helpers: BIO encoding of char spans and decoding back to char spans."""
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer
from .data import LABELS

TAGS = ["O"] + [f"{p}-{l}" for l in LABELS for p in "BI"]
T2I = {t: i for i, t in enumerate(TAGS)}
MAXLEN = 128


def load(name_or_dir):
    tok = AutoTokenizer.from_pretrained(name_or_dir)
    model = AutoModelForTokenClassification.from_pretrained(
        name_or_dir, num_labels=len(TAGS), id2label=dict(enumerate(TAGS)), label2id=T2I)
    return tok, model


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

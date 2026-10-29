"""Tests for symptom model loading, error handling, and baseline fallback."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.symptoms.model import (
    is_local_path, validate_local_model_dir, load,
    ModelNotFoundError, ModelLoadError
)
from src.symptoms.infer import Extractor, structure


class TestModelLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_local_path(self):
        self.assertTrue(is_local_path("models/modernbert_f100_s1"))
        self.assertTrue(is_local_path("./models/test"))
        self.assertTrue(is_local_path("C:\\Users\\test\\models"))
        self.assertTrue(is_local_path("/tmp/model"))
        self.assertFalse(is_local_path("answerdotai/ModernBERT-base") and not Path("answerdotai/ModernBERT-base").exists())

    def test_missing_model_directory_raises_not_found(self):
        non_existent = Path(self.temp_dir) / "missing_checkpoint"
        with self.assertRaises(ModelNotFoundError) as ctx:
            validate_local_model_dir(non_existent)
        err = str(ctx.exception)
        self.assertIn("Model directory not found", err)
        self.assertIn("train_all", err)

    def test_incomplete_model_directory_raises_load_error(self):
        incomplete_dir = Path(self.temp_dir) / "empty_model"
        incomplete_dir.mkdir(parents=True, exist_ok=True)
        # Directory exists but has no config.json or weights
        with self.assertRaises(ModelLoadError) as ctx:
            validate_local_model_dir(incomplete_dir)
        err = str(ctx.exception)
        self.assertIn("incomplete or malformed", err)
        self.assertIn("config.json", err)

    def test_extractor_missing_model_strict_mode(self):
        non_existent = Path(self.temp_dir) / "missing_model"
        with self.assertRaises(ModelNotFoundError):
            Extractor(str(non_existent), fallback_to_baseline=False)

    def test_extractor_fallback_to_baseline(self):
        non_existent = Path(self.temp_dir) / "missing_model"
        ext = Extractor(str(non_existent), fallback_to_baseline=True)
        self.assertEqual(ext.mode, "baseline")

        res = ext.extract("no fever but cough for 3 days, mild headache")
        self.assertEqual(res["extractor_mode"], "baseline")

        # Verify symptoms extracted
        sym_texts = {s["text"]: s["negated"] for s in res["symptoms"]}
        self.assertIn("fever", sym_texts)
        self.assertTrue(sym_texts["fever"])  # Negated: True
        self.assertIn("cough", sym_texts)
        self.assertFalse(sym_texts["cough"])  # Negated: False
        self.assertIn("headache", sym_texts)
        self.assertFalse(sym_texts["headache"])

        # Verify duration and severity
        self.assertTrue(any("3 days" in d["text"] for d in res["durations"]))
        self.assertTrue(any("mild" in v["text"] for v in res["severities"]))

    def test_structure_helper(self):
        text = "fever for 2 days"
        spans = [
            {"start": 0, "end": 5, "label": "SYMPTOM"},
            {"start": 10, "end": 16, "label": "DURATION"}
        ]
        structured = structure(text, spans)
        self.assertEqual(len(structured["symptoms"]), 1)
        self.assertEqual(structured["symptoms"][0]["text"], "fever")
        self.assertFalse(structured["symptoms"][0]["negated"])
        self.assertEqual(len(structured["durations"]), 1)
        self.assertEqual(structured["durations"][0]["text"], "2 days")


if __name__ == "__main__":
    unittest.main()

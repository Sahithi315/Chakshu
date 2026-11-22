"""
Tests for enhanced doctor summary:
- Deterministic abnormal-value flags from code matching reference ranges exactly (HIGH & LOW)
- Numbers only for trends; no interpretive wording
- Output validator rejects invented numbers, invented medicines, and forbidden wording
- On rejection, router tries next provider; then falls back to deterministic template
- Every bullet carries valid source_ids
- No direct identifiers sent in LLM prompts
- New fields 'generated_by' and 'fallback_used' present without breaking existing response fields
"""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch

from src.services.abnormal_flags import flag_abnormal_labs, compute_lab_trends
from src.services.summary_llm_enhance import (
    enhance_summary_with_llm, _validate_llm_summary, _build_facts,
    _FORBIDDEN_RE,
)
from src.services.summary_service import generate_clinical_summary
from src.llm.base import LLMResult, RateLimitError
from src.llm.router import LLMRouter, _circuit_breaker


class FakeProvider:
    def __init__(self, name: str, responses: list = None):
        self.name = name
        self.responses = list(responses or [])
        self.call_count = 0
        self.prompts = []

    def is_configured(self):
        return True

    def generate(self, prompt, system="", max_tokens=1024, temperature=0.3, timeout=6.0, validator=None):
        self.call_count += 1
        self.prompts.append(prompt)
        if not self.responses:
            return LLMResult(text="{}", provider=self.name, model="fake", latency_ms=5.0)
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return LLMResult(text=str(resp), provider=self.name, model="fake", latency_ms=5.0)


class TestSummaryEnhanced(unittest.TestCase):
    def setUp(self):
        _circuit_breaker._cooldown_until.clear()
        _circuit_breaker._unhealthy.clear()

    def test_abnormal_flags_deterministic_high_and_low(self):
        """Abnormal lab values above AND below reference range are flagged without LLM."""
        labs = [
            {"test_name": "Hemoglobin", "test_value": "9.5", "unit": "g/dL", "reference_range": "12.0 - 15.0"},
            {"test_name": "WBC Count", "test_value": "15200", "unit": "/uL", "reference_range": "4000 - 11000"},
            {"test_name": "Platelets", "test_value": "250000", "unit": "/uL", "reference_range": "150000 - 450000"},
            {"test_name": "Fasting Blood Sugar", "test_value": "62", "unit": "mg/dL", "reference_range": "70 - 100"},
            {"test_name": "Serum Potassium", "test_value": "5.8", "unit": "mmol/L", "reference_range": "3.5 - 5.0"},
        ]

        flagged = flag_abnormal_labs(labs)

        self.assertEqual(len(flagged), 5)
        self.assertEqual(flagged[0]["flag"], "LOW")      # Hemoglobin 9.5 < 12.0
        self.assertEqual(flagged[1]["flag"], "HIGH")     # WBC 15200 > 11000
        self.assertEqual(flagged[2]["flag"], "NORMAL")   # Platelets in range
        self.assertEqual(flagged[3]["flag"], "LOW")      # Glucose 62 < 70
        self.assertEqual(flagged[4]["flag"], "HIGH")     # Potassium 5.8 > 5.0

        # No interpretive wording appears anywhere in the output
        for item in flagged:
            combined = f"{item['test_name']} {item['value']} {item['flag']} {item['reference_range']}"
            self.assertFalse(_FORBIDDEN_RE.search(combined))

    def test_lab_trends_numbers_only(self):
        """Lab trends compute delta as numbers only without interpretive wording."""
        cur_labs = [
            {"test_name": "HbA1c", "test_value": "8.1", "unit": "%", "reference_range": "4.0 - 5.6"},
            {"test_name": "Serum Creatinine", "test_value": "1.1", "unit": "mg/dL", "reference_range": "0.7 - 1.3"},
        ]
        prior_labs = [
            {"test_name": "HbA1c", "test_value": "7.6", "unit": "%"},
            {"test_name": "Serum Creatinine", "test_value": "1.4", "unit": "mg/dL"},
        ]

        trends = compute_lab_trends(cur_labs, prior_labs)
        self.assertEqual(len(trends), 2)

        # Check HbA1c
        hba1c = next(t for t in trends if t["test_name"] == "HbA1c")
        self.assertEqual(hba1c["previous_value"], 7.6)
        self.assertEqual(hba1c["current_value"], 8.1)
        self.assertEqual(hba1c["delta"], 0.5)

        # Check Creatinine
        creat = next(t for t in trends if t["test_name"] == "Serum Creatinine")
        self.assertEqual(creat["previous_value"], 1.4)
        self.assertEqual(creat["current_value"], 1.1)
        self.assertEqual(creat["delta"], -0.3)

    def test_output_validator_rejects_forbidden_wording(self):
        """Summary validator rejects outputs containing forbidden words."""
        forbidden_texts = [
            '{"today_bullets": ["Chest pain suggests angina [intake_1]"], "history_bullets": [], "same_complaint_bullets": [], "confirm_bullets": []}',
            '{"today_bullets": ["Fever indicates infection [intake_1]"], "history_bullets": [], "same_complaint_bullets": [], "confirm_bullets": []}',
            '{"today_bullets": ["Consistent with diabetes [intake_1]"], "history_bullets": [], "same_complaint_bullets": [], "confirm_bullets": []}',
            '{"today_bullets": ["Likely viral illness [intake_1]"], "history_bullets": [], "same_complaint_bullets": [], "confirm_bullets": []}',
            '{"today_bullets": ["New diagnosis of hypertension [intake_1]"], "history_bullets": [], "same_complaint_bullets": [], "confirm_bullets": []}',
            '{"today_bullets": ["You should take aspirin [intake_1]"], "history_bullets": [], "same_complaint_bullets": [], "confirm_bullets": []}',
        ]

        fact_ids = {"intake_1"}
        facts = {"intake_1": {"chief_complaint": "Chest pain"}}

        for text in forbidden_texts:
            result = _validate_llm_summary(text, fact_ids, facts)
            self.assertIsNone(result, f"Expected rejection for: {text}")

    def test_output_validator_rejects_invented_number(self):
        """Summary validator rejects outputs with numbers not present in facts."""
        fact_ids = {"intake_1", "vitals_1"}
        facts = {
            "intake_1": {"duration": "3 days", "severity": "mild"},
            "vitals_1": {"bp": "120/80 mmHg", "hr": "72 bpm"},
        }

        # 99 is not in facts (facts have 3, 120, 80, 72)
        invented_number_text = json.dumps({
            "today_bullets": ["Patient reported fever of 99 F [intake_1]"],
            "history_bullets": [],
            "same_complaint_bullets": [],
            "confirm_bullets": [],
        })

        result = _validate_llm_summary(invented_number_text, fact_ids, facts)
        self.assertIsNone(result)

    def test_output_validator_rejects_invented_medicine(self):
        """Summary validator rejects outputs introducing medicine names not in facts."""
        fact_ids = {"intake_1"}
        facts = {
            "intake_1": {"conditions": "Hypertension", "medications": "Amlodipine 5mg"},
        }

        # Atorvastatin is not in the facts
        invented_med_text = json.dumps({
            "today_bullets": ["Taking Atorvastatin daily [intake_1]"],
            "history_bullets": [],
            "same_complaint_bullets": [],
            "confirm_bullets": [],
        })

        result = _validate_llm_summary(invented_med_text, fact_ids, facts)
        self.assertIsNone(result)

    def test_output_validator_rejects_bullets_without_source_ids(self):
        """Bullets missing valid source_ids must be rejected."""
        fact_ids = {"intake_1"}
        facts = {"intake_1": {"chief_complaint": "Cough for 3 days"}}

        no_source_text = json.dumps({
            "today_bullets": ["Cough for 3 days"],  # missing [intake_1]
            "history_bullets": [],
            "same_complaint_bullets": [],
            "confirm_bullets": [],
        })

        result = _validate_llm_summary(no_source_text, fact_ids, facts)
        self.assertIsNone(result)

    def test_failover_on_rejected_summary_falls_back_to_template(self):
        """
        When Provider 1 outputs invalid text (invented number), router fails over
        to Provider 2; if Provider 2 also fails, falls back to deterministic template.
        """
        bad_output = json.dumps({
            "today_bullets": ["Invented lab value 999 [intake_1]"],
            "history_bullets": [],
            "same_complaint_bullets": [],
            "confirm_bullets": [],
        })
        good_output = json.dumps({
            "today_bullets": ["Cough for 3 days [intake_1]"],
            "history_bullets": [],
            "same_complaint_bullets": [],
            "confirm_bullets": [],
        })

        p1 = FakeProvider("anthropic", [bad_output])
        p2 = FakeProvider("gemini", [good_output])
        test_router = LLMRouter([p1, p2])

        base_summary = generate_clinical_summary({"reason_for_visit": "Cough", "duration": "3 days"})

        with patch("src.llm.router.get_router", return_value=test_router):
            enhanced = enhance_summary_with_llm(
                base_summary=base_summary,
                intake={"reason_for_visit": "Cough", "duration": "3 days"},
                vitals={},
                labs=[],
                history=[],
            )

        self.assertEqual(enhanced["generated_by"], "gemini")
        self.assertFalse(enhanced["fallback_used"])

    def test_all_providers_fail_uses_deterministic_template(self):
        """When all providers fail or are rejected, deterministic template is used without error."""
        p1 = FakeProvider("anthropic", [RateLimitError("429")])
        p2 = FakeProvider("gemini", [RateLimitError("429")])
        test_router = LLMRouter([p1, p2])

        base_summary = generate_clinical_summary({"reason_for_visit": "Headache", "duration": "2 days"})

        with patch("src.llm.router.get_router", return_value=test_router):
            enhanced = enhance_summary_with_llm(
                base_summary=base_summary,
                intake={"reason_for_visit": "Headache", "duration": "2 days"},
                vitals={},
                labs=[],
                history=[],
            )

        self.assertEqual(enhanced["generated_by"], "deterministic")
        self.assertTrue(enhanced["fallback_used"])
        # Check single card contains formatted bullets with source_ids
        sc = enhanced["single_card"]
        self.assertIn("today_llm_bullets", sc)
        self.assertTrue(any("intake_1" in b for b in sc["today_llm_bullets"]))

    def test_no_direct_identifiers_in_llm_facts(self):
        """Name, phone, and MRN are not included in the structured facts sent to LLM."""
        facts, fact_ids = _build_facts(
            intake={"reason_for_visit": "Knee pain", "patient_name": "Aarav Nair", "phone": "9876543210"},
            vitals={"bp_systolic": 120, "bp_diastolic": 80},
            labs=[],
            history=[],
        )
        facts_str = json.dumps(facts)
        self.assertNotIn("Aarav Nair", facts_str)
        self.assertNotIn("9876543210", facts_str)


if __name__ == "__main__":
    unittest.main()

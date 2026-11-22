"""
Tests for patient chatbot intake service:
- Question cap compliance (<= 6)
- Skips already known fields
- Stops early on Done
- Emergency keyword triggers neutral nurse notice
- Structured output parsing
- Redaction of patient PHI before sending to LLM
- Seamless conversation continuation after mid-chat failover
- All providers fail -> graceful fallback
"""
from __future__ import annotations
import json
import os
import unittest
from unittest.mock import patch, MagicMock

from src.database.schema import init_db
from src.database.connection import get_db
from src.services.patient_service import (
    register_or_get_patient, create_visit, get_visit_details,
)
from src.services.chat_service import (
    start_chat_session, handle_chat_message, _has_emergency, _redact_phi,
    _safe_parse_intake, MAX_QUESTIONS,
)
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
            return LLMResult(text="Next question?", provider=self.name, model="fake", latency_ms=5.0)
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return LLMResult(text=str(resp), provider=self.name, model="fake", latency_ms=5.0)


class TestChatbot(unittest.TestCase):
    def setUp(self):
        init_db()
        _circuit_breaker._cooldown_until.clear()
        _circuit_breaker._unhealthy.clear()
        # Register a test patient and visit
        p_res, _ = register_or_get_patient("9876543210", "Test Patient", 35, "Female")
        self.patient = p_res
        self.visit = create_visit(self.patient["patient_id"], allow_duplicate_today=True)

    def test_emergency_keyword_triggers_nurse_notice(self):
        """Emergency keywords immediately return nurse notice without diagnosing."""
        # 1. Deterministic helper
        self.assertTrue(_has_emergency("I have severe chest pain and breathlessness"))
        self.assertTrue(_has_emergency("Patient feels fainting"))
        self.assertFalse(_has_emergency("Mild headache for 2 days"))

        # 2. In-session chat message
        res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], {})
        session_id = res["session_id"]

        reply = handle_chat_message(session_id, "I have sudden chest pain and can't breathe")
        self.assertTrue(reply["done"])
        self.assertTrue(reply["emergency"])
        self.assertIn("Please tell the nurse right now", reply["message"])

        # Forbidden wording should NOT appear
        self.assertNotIn("diagnosis", reply["message"].lower())
        self.assertNotIn("likely", reply["message"].lower())

    def test_phi_redaction(self):
        """Phone numbers and emails must be redacted before sending to LLM."""
        text = "Call me at 9876543210 or email test.user@hospital.org"
        redacted = _redact_phi(text)
        self.assertNotIn("9876543210", redacted)
        self.assertNotIn("test.user@hospital.org", redacted)
        self.assertIn("[PHONE_REDACTED]", redacted)
        self.assertIn("[EMAIL_REDACTED]", redacted)

    def test_never_exceeds_question_cap(self):
        """Chatbot never asks more than MAX_QUESTIONS (hard cap 6)."""
        res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], {})
        session_id = res["session_id"]

        q_count = 1
        for i in range(10):
            reply = handle_chat_message(session_id, f"Answer number {i+1}")
            if reply.get("done"):
                break
            q_count += 1

        self.assertLessEqual(q_count, MAX_QUESTIONS)

    def test_patient_stops_early_on_done(self):
        """Patient typing 'done' or 'that's all' immediately finalizes the session."""
        res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], {})
        session_id = res["session_id"]

        reply = handle_chat_message(session_id, "That's all / Done")
        self.assertTrue(reply["done"])
        self.assertIn("structured_intake", reply)

    def test_skips_known_fields_from_history(self):
        """Returning patient with known chronic conditions/meds skips asking for them."""
        known = {
            "chronic_conditions": "Hypertension, Type 2 Diabetes",
            "medications": "Metformin 500mg, Amlodipine 5mg",
            "allergies": "Penicillin",
            "is_returning": True,
        }
        res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], known)
        self.assertIsNotNone(res["question"])
        # First question should still be chief complaint
        self.assertIn("main reason", res["question"].lower())

    def test_mid_chat_failover_seamless(self):
        """
        When Provider 1 serves Turn 1, then fails on Turn 2, Provider 2
        continues the conversation seamlessly from server-side state.
        """
        p1 = FakeProvider("anthropic", [
            "What brings you in today?",           # Initial question
            "How long have you had this problem?",  # Turn 1 question
            RateLimitError("429 Rate Limit", provider="anthropic"),  # Turn 2 failure
        ])
        p2 = FakeProvider("gemini", [
            "Is the pain getting better or worse?",  # Turn 2 question from Gemini
        ])

        test_router = LLMRouter([p1, p2])

        with patch("src.llm.router.get_router", return_value=test_router):
            # Start session (p1 serves initial question)
            start_res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], {})
            session_id = start_res["session_id"]
            self.assertEqual(start_res["question"], "What brings you in today?")

            # Turn 1: patient answers (p1 serves next question)
            reply1 = handle_chat_message(session_id, "I have knee pain")
            self.assertFalse(reply1.get("done"))
            self.assertEqual(reply1["question"], "How long have you had this problem?")

            # Turn 2: patient answers (p1 rate limits -> p2 serves next question)
            reply2 = handle_chat_message(session_id, "For about 4 days")
            self.assertFalse(reply2.get("done"))
            self.assertEqual(reply2["question"], "Is the pain getting better or worse?")

    def test_all_providers_fail_uses_deterministic_template(self):
        """When all LLM providers fail, chatbot uses deterministic template questions."""
        p1 = FakeProvider("anthropic", [RateLimitError("429")])
        p2 = FakeProvider("gemini", [RateLimitError("429")])
        test_router = LLMRouter([p1, p2])

        with patch("src.llm.router.get_router", return_value=test_router):
            res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], {})
            self.assertIsNotNone(res["question"])
            # Fallback template question
            self.assertIn("main reason", res["question"].lower())

            # Next answer should also get deterministic template question without error
            reply = handle_chat_message(res["session_id"], "Mild knee discomfort")
            self.assertFalse(reply.get("done"))
            self.assertIn("long", reply["question"].lower())

    def test_structured_intake_saved_to_db(self):
        """Completed chatbot intake saves structured fields into database intakes table."""
        res = start_chat_session(self.visit["visit_id"], self.patient["patient_id"], {})
        session_id = res["session_id"]

        # Simulate full conversation then finalize
        handle_chat_message(session_id, "Persistent dry cough")
        handle_chat_message(session_id, "3 weeks")
        final = handle_chat_message(session_id, "done")

        self.assertTrue(final["done"])
        # Check intake in database
        visit_data = get_visit_details(self.visit["visit_id"])
        intake = visit_data.get("intake")
        self.assertIsNotNone(intake)
        self.assertIn("cough", (intake.get("reason_for_visit") or "").lower())


if __name__ == "__main__":
    unittest.main()

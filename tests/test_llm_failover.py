"""
Tests for LLM failover routing, circuit breaker, rate limit, timeout, and 5xx handling.
Uses fake providers with zero real network calls.
"""
from __future__ import annotations
import os
import time
import unittest
from unittest.mock import patch

from src.llm.base import (
    LLMProvider, LLMResult, RateLimitError, QuotaExhaustedError,
    TimeoutError as LLMTimeoutError, ServerError, AuthError, BadRequestError,
)
from src.llm.router import LLMRouter, _circuit_breaker


class FakeProvider(LLMProvider):
    def __init__(self, name: str, responses: list = None, configured: bool = True):
        self.name = name
        self._configured = configured
        self._responses = list(responses or [])
        self.call_count = 0
        self.prompts_received = []

    def is_configured(self) -> bool:
        return self._configured

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3, timeout: float = 6.0) -> LLMResult:
        self.call_count += 1
        self.prompts_received.append((prompt, system))
        if not self._responses:
            return LLMResult(text=f"Default reply from {self.name}", provider=self.name, model="fake-model", latency_ms=10.0)
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return LLMResult(text=str(resp), provider=self.name, model="fake-model", latency_ms=10.0)


class TestLLMFailover(unittest.TestCase):
    def setUp(self):
        # Reset circuit breaker state for each test
        _circuit_breaker._cooldown_until.clear()
        _circuit_breaker._unhealthy.clear()

    def test_first_rate_limited_second_serves(self):
        """First provider rate-limited -> second provider serves the response."""
        p1 = FakeProvider("anthropic", [RateLimitError("429 Too Many Requests", provider="anthropic", retry_after=30.0)])
        p2 = FakeProvider("gemini", ["Valid response from Gemini"])
        p3 = FakeProvider("openai", ["Valid response from OpenAI"])

        router = LLMRouter([p1, p2, p3])
        result = router.generate("What are my symptoms?")

        self.assertIsNotNone(result)
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.text, "Valid response from Gemini")
        self.assertEqual(p1.call_count, 1)
        self.assertEqual(p2.call_count, 1)
        self.assertEqual(p3.call_count, 0)

        # Provider 1 should now be in cooldown
        self.assertFalse(_circuit_breaker.is_available("anthropic"))

    def test_timeout_and_5xx_failover(self):
        """Timeout on p1, 5xx on p2 -> failover to p3."""
        p1 = FakeProvider("anthropic", [
            LLMTimeoutError("Read timed out", provider="anthropic"),
            LLMTimeoutError("Read timed out retry", provider="anthropic"),
        ])
        p2 = FakeProvider("gemini", [
            ServerError("500 Internal Server Error", provider="gemini"),
            ServerError("500 Internal Server Error retry", provider="gemini"),
        ])
        p3 = FakeProvider("openai", ["OpenAI recovered successfully"])

        router = LLMRouter([p1, p2, p3])
        with patch("time.sleep"):  # Skip real sleep for jittered retries
            result = router.generate("Hello")

        self.assertIsNotNone(result)
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.text, "OpenAI recovered successfully")

    def test_cooldown_skip_and_recovery(self):
        """Provider in cooldown is skipped; recovers after cooldown expires."""
        p1 = FakeProvider("anthropic", [RateLimitError("Rate limit", retry_after=1.0)])
        p2 = FakeProvider("gemini", ["Gemini answer 1", "Gemini answer 2"])

        router = LLMRouter([p1, p2])
        # First call triggers rate limit on p1
        res1 = router.generate("Question 1")
        self.assertEqual(res1.provider, "gemini")

        # Second call immediately: p1 in cooldown, skipped without calling
        res2 = router.generate("Question 2")
        self.assertEqual(res2.provider, "gemini")
        self.assertEqual(p1.call_count, 1)  # Was not called a 2nd time

        # Simulate cooldown expiry
        _circuit_breaker.reset("anthropic")
        p1._responses = ["Anthropic is back!"]
        res3 = router.generate("Question 3")
        self.assertEqual(res3.provider, "anthropic")
        self.assertEqual(res3.text, "Anthropic is back!")

    def test_auth_error_marks_unhealthy_skips(self):
        """Auth error marks provider permanently unhealthy until reset, moves to next."""
        p1 = FakeProvider("anthropic", [AuthError("Invalid API key", provider="anthropic")])
        p2 = FakeProvider("gemini", ["Gemini worked"])

        router = LLMRouter([p1, p2])
        res = router.generate("Prompt")
        self.assertEqual(res.provider, "gemini")
        self.assertTrue("anthropic" in _circuit_breaker._unhealthy)
        self.assertFalse(_circuit_breaker.is_available("anthropic"))

    def test_all_providers_fail_returns_none(self):
        """When all providers fail, router returns None (no exception raised)."""
        p1 = FakeProvider("anthropic", [
            RateLimitError("429"), RateLimitError("429")
        ])
        p2 = FakeProvider("gemini", [
            ServerError("500"), ServerError("500")
        ])
        router = LLMRouter([p1, p2])
        with patch("time.sleep"):
            result = router.generate("Prompt")
        self.assertIsNone(result)

    def test_unconfigured_provider_skipped(self):
        """Provider without API key is skipped."""
        p1 = FakeProvider("anthropic", configured=False)
        p2 = FakeProvider("gemini", ["Answer"])
        router = LLMRouter([p1, p2])
        res = router.generate("Prompt")
        self.assertEqual(res.provider, "gemini")
        self.assertEqual(p1.call_count, 0)

    def test_health_status_format(self):
        """Router status reports per-provider health without exposing keys."""
        p1 = FakeProvider("anthropic", configured=True)
        p2 = FakeProvider("gemini", configured=False)
        router = LLMRouter([p1, p2])
        st = router.status()
        self.assertEqual(len(st), 2)
        self.assertEqual(st[0]["provider"], "anthropic")
        self.assertTrue(st[0]["configured"])
        self.assertTrue(st[0]["available"])
        self.assertFalse(st[1]["configured"])


if __name__ == "__main__":
    unittest.main()

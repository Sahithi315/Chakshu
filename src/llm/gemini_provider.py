"""Google Gemini provider — maps SDK exceptions to normalized errors."""
from __future__ import annotations
import os
import time
from .base import LLMProvider, LLMResult, RateLimitError, QuotaExhaustedError
from .base import TimeoutError as LLMTimeoutError, ServerError, AuthError, BadRequestError, LLMError


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        self._model = None
        self._model_name_cached = ""

    def is_configured(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())

    def _get_model(self, model_name: str):
        try:
            import google.generativeai as genai
            if self._model_name_cached != model_name:
                genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
                self._model = genai.GenerativeModel(model_name)
                self._model_name_cached = model_name
            return self._model
        except ImportError:
            raise LLMError("google-generativeai package not installed", provider=self.name)

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3, timeout: float = 6.0) -> LLMResult:
        try:
            import google.generativeai as genai
            model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            model = self._get_model(model_name)
            t0 = time.monotonic()
            config = genai.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature)
            resp = model.generate_content(
                full_prompt,
                generation_config=config,
                request_options={"timeout": timeout},
            )
            latency_ms = (time.monotonic() - t0) * 1000
            text = resp.text if hasattr(resp, "text") else ""
            return LLMResult(text=text, provider=self.name, model=model_name, latency_ms=latency_ms)
        except Exception as e:
            msg = str(e).lower()
            ename = type(e).__name__.lower()
            if "quota" in msg or "resource_exhausted" in ename or "resourceexhausted" in ename:
                raise QuotaExhaustedError(str(e), provider=self.name, retry_after=3600.0)
            if ("rate" in msg and "limit" in msg) or "429" in msg:
                raise RateLimitError(str(e), provider=self.name, retry_after=60.0)
            if "unauthenticated" in ename or "permissiondenied" in ename or "api_key" in msg:
                raise AuthError(str(e), provider=self.name)
            if "deadline" in msg or "timeout" in msg:
                raise LLMTimeoutError(str(e), provider=self.name)
            if "internal" in msg or "unavailable" in ename or "serviceunavailable" in ename:
                raise ServerError(str(e), provider=self.name)
            raise LLMError(f"Gemini error: {e}", provider=self.name)

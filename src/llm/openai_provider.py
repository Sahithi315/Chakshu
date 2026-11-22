"""OpenAI provider — maps SDK exceptions to normalized errors."""
from __future__ import annotations
import os
import time
from .base import LLMProvider, LLMResult, RateLimitError, QuotaExhaustedError
from .base import TimeoutError as LLMTimeoutError, ServerError, AuthError, BadRequestError, LLMError


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY", ""),
                )
            except ImportError:
                raise LLMError("openai package not installed", provider=self.name)
        return self._client

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3, timeout: float = 6.0) -> LLMResult:
        try:
            client = self._client_or_raise()
            model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            t0 = time.monotonic()
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            text = resp.choices[0].message.content if resp.choices else ""
            usage = resp.usage
            return LLMResult(
                text=text,
                provider=self.name,
                model=model,
                latency_ms=latency_ms,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            )
        except Exception as e:
            ename = type(e).__name__
            msg_str = str(e)
            if ename == "RateLimitError":
                retry_after = 60.0
                try:
                    if hasattr(e, "response") and e.response is not None:
                        retry_after = float(e.response.headers.get("retry-after", 60))
                except Exception:
                    pass
                raise RateLimitError(msg_str, provider=self.name, retry_after=retry_after)
            if ename == "AuthenticationError":
                raise AuthError(msg_str, provider=self.name)
            if ename == "BadRequestError":
                raise BadRequestError(msg_str, provider=self.name)
            if ename == "InternalServerError":
                raise ServerError(msg_str, provider=self.name)
            if ename in ("APITimeoutError",):
                raise LLMTimeoutError(msg_str, provider=self.name)
            if ename == "APIConnectionError":
                raise ServerError(msg_str, provider=self.name)
            if hasattr(e, "status_code"):
                sc = e.status_code
                if sc == 429:
                    raise RateLimitError(msg_str, provider=self.name, retry_after=60.0)
                if sc and sc >= 500:
                    raise ServerError(msg_str, provider=self.name)
            raise LLMError(f"OpenAI error: {e}", provider=self.name)

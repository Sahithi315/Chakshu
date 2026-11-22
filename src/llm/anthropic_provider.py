"""Anthropic Claude provider — maps SDK exceptions to normalized errors."""
from __future__ import annotations
import os
import time
from .base import LLMProvider, LLMResult, RateLimitError, QuotaExhaustedError
from .base import TimeoutError as LLMTimeoutError, ServerError, AuthError, BadRequestError, LLMError


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self):
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                )
            except ImportError:
                raise LLMError("anthropic package not installed", provider=self.name)
        return self._client

    def is_configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3, timeout: float = 6.0) -> LLMResult:
        try:
            import anthropic
            client = self._client_or_raise()
            model = os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            t0 = time.monotonic()
            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            if system:
                kwargs["system"] = system
            msg = client.messages.create(**kwargs, timeout=timeout)
            latency_ms = (time.monotonic() - t0) * 1000
            text = msg.content[0].text if msg.content else ""
            return LLMResult(
                text=text,
                provider=self.name,
                model=model,
                latency_ms=latency_ms,
                prompt_tokens=msg.usage.input_tokens if msg.usage else 0,
                completion_tokens=msg.usage.output_tokens if msg.usage else 0,
            )
        except Exception as e:
            # Normalize by exception class name (works without anthropic installed)
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
            raise LLMError(f"Anthropic error: {e}", provider=self.name)

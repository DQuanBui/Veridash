"""Thin wrapper around the Google Gen AI SDK for Gemini.

Responsibilities:

* resolve the API key (sidebar session value first, then ``st.secrets``),
* enforce a per-session call budget,
* retry transient failures (429 / 5xx) with exponential backoff,
* request structured JSON output and parse it,
* turn SDK errors into short, user-safe messages that never include the key.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, MutableMapping
from typing import Any

from core.settings import AI_TIMEOUT_S, DEFAULT_GEMINI_MODEL, MAX_AI_CALLS_PER_SESSION

CALLS_KEY = "vd_ai_calls"
RETRYABLE = {429, 500, 502, 503, 504}


class AIError(RuntimeError):
    """An AI request failed. The message is safe to show to users."""


def _secret(name: str) -> str | None:
    """Read a value from ``st.secrets`` or the environment, without raising."""
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:  # no secrets file configured
        pass
    value = os.environ.get(name)
    return value or None


def resolve_api_key(session_key: str | None) -> tuple[str | None, str | None]:
    """Return ``(key, source)`` where source is ``"session"``, ``"secrets"`` or ``None``."""
    if session_key:
        return session_key, "session"
    secret = _secret("GEMINI_API_KEY")
    if secret:
        return secret, "secrets"
    return None, None


def resolve_model() -> str:
    """The configured Gemini model (``GEMINI_MODEL`` secret) or the default."""
    return _secret("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL


def _default_factory(api_key: str) -> Any:
    from google import genai
    from google.genai import types

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(AI_TIMEOUT_S * 1000)))


def _friendly(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if code in (400, 401) and "API key" in str(exc):
        return "The Gemini API key was rejected. Check that it is correct and active."
    if code == 403:
        return "The Gemini API key does not have permission for this model."
    if code == 404:
        return "The configured Gemini model was not found. Check the GEMINI_MODEL setting."
    if code == 429:
        return "Gemini's rate limit or quota was reached. Try again in a minute."
    if code is not None and code >= 500:
        return "Gemini is temporarily unavailable. Try again shortly."
    if code is not None:
        return f"Gemini returned an error (HTTP {code})."
    return "Gemini could not be reached."


class GeminiClient:
    """Structured-output Gemini calls with retries and a per-session budget.

    Args:
        api_key: The Gemini API key (never logged).
        model: Model name, e.g. ``gemini-3.6-flash``.
        counter: A mutable mapping (``st.session_state`` in the app) that
            stores how many calls this session has made.
        max_calls: Session budget.
        client_factory: Builds the SDK client; injectable for tests.
        sleep: Backoff sleep function; injectable for tests.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        counter: MutableMapping[str, Any],
        max_calls: int = MAX_AI_CALLS_PER_SESSION,
        max_retries: int = 3,
        client_factory: Callable[[str], Any] = _default_factory,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self._counter = counter
        self._max_calls = max_calls
        self._max_retries = max_retries
        self._sleep = sleep
        self._client = client_factory(api_key)

    @property
    def calls_used(self) -> int:
        """Calls made so far in this session."""
        return int(self._counter.get(CALLS_KEY, 0))

    @property
    def calls_left(self) -> int:
        """Calls remaining in this session's budget."""
        return max(0, self._max_calls - self.calls_used)

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str) -> dict[str, Any]:
        """Send one prompt and return the parsed JSON object.

        Raises:
            AIError: On budget exhaustion, API failure or invalid JSON.
        """
        if self.calls_left <= 0:
            raise AIError(f"This session has used its {self._max_calls} AI calls. Reload the page to start a new session.")
        self._counter[CALLS_KEY] = self.calls_used + 1

        config = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "temperature": 0.2,
        }
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
                text = getattr(response, "text", None)
                if not text:
                    raise AIError("Gemini returned an empty response.")
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise AIError("Gemini returned a response that was not valid JSON.") from exc
            except AIError:
                raise
            except Exception as exc:
                last_exc = exc
                code = getattr(exc, "code", None)
                if code in RETRYABLE and attempt < self._max_retries - 1:
                    self._sleep(2**attempt)
                    continue
                raise AIError(_friendly(exc)) from exc
        raise AIError(_friendly(last_exc or RuntimeError()))  # pragma: no cover

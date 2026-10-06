"""OpenAI-compatible chat completions for workflow prompt steps.

The API key is never bundled: it comes from the user's config (``ai.api_key``)
or the ``OPENAI_API_KEY`` environment variable. Keys are never logged and
never appear in error messages.
"""

import os
from typing import Dict, Optional

from ..core import exceptions

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 120


class LLMError(exceptions.AIError):
    """Raised when an LLM request fails."""


def resolve_api_key(configured: Optional[str] = None) -> str:
    """Return the first available API key, or raise."""
    key = (configured or os.environ.get(OPENAI_API_KEY_ENV) or "").strip()
    if not key:
        raise LLMError(
            "No API key configured. Set one in Settings -> AI, or set the "
            "OPENAI_API_KEY environment variable."
        )
    return key


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat-client used by prompt steps."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session=None,
    ):
        from ..core import config

        settings = config.get_config().ai
        self.base_url = (base_url or settings.base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = None if api_key is None else api_key.strip()
        self.timeout = timeout
        self._session = session

    def _request_session(self):
        if self._session is not None:
            return self._session
        import requests

        self._session = requests.Session()
        return self._session

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion and return the assistant's message text."""
        key = resolve_api_key(self.api_key)
        messages: list = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        session = self._request_session()
        url = f"{self.base_url}/chat/completions"
        payload: Dict = {
            "model": model or DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            response = session.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
                timeout=self.timeout,
            )
        except Exception as error:
            raise LLMError(f"LLM request failed: {error}") from error

        if response.status_code == 401:
            raise LLMError("LLM authorization failed: check your API key.")
        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = str(body.get("error", {}).get("message", ""))[:300]
            except ValueError:
                detail = response.text[:300]
            raise LLMError(f"LLM returned HTTP {response.status_code}: {detail}")

        try:
            body = response.json()
            return str(body["choices"][0]["message"]["content"]).strip()
        except (ValueError, KeyError, IndexError) as error:
            raise LLMError("LLM returned an unexpected response shape") from error
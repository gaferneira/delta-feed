"""Adapter for OpenAI-compatible chat completion servers such as LM Studio.

Only the endpoint configured here is contacted. Pointing it at a hosted service
sends article text there, so that is an explicit configuration choice, never a
fallback.
"""

import os
from typing import TypeVar

import requests
from django.conf import settings
from pydantic import BaseModel

from delta_feed.analysis.contracts.extraction import ExtractionResult
from delta_feed.analysis.providers import InferenceUnavailableError

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class OpenAICompatibleLanguageModel:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (
            base_url if base_url is not None else os.environ.get("OPENAI_COMPAT_BASE_URL")
        )
        self.model = model if model is not None else os.environ.get("OPENAI_COMPAT_MODEL")
        # Local servers such as LM Studio need no key.
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_COMPAT_API_KEY")
        self.timeout = timeout if timeout is not None else settings.ANALYSIS_TIMEOUT_SECONDS

    @property
    def model_version(self) -> str:
        return f"openai-compatible:{self.model}" if self.model else "openai-compatible:unconfigured"

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    def analyze(
        self,
        prompt: str,
        output_schema: type[OutputModel] = ExtractionResult,
    ) -> OutputModel:
        if not self.base_url:
            raise InferenceUnavailableError(
                "inference unavailable: OPENAI_COMPAT_BASE_URL is not configured"
            )
        if not self.model:
            raise InferenceUnavailableError(
                "inference unavailable: OPENAI_COMPAT_MODEL is not configured"
            )
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": output_schema.__name__,
                            "strict": True,
                            "schema": output_schema.model_json_schema(),
                        },
                    },
                    # Extraction should be repeatable, not creative.
                    "temperature": 0,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            output_text = response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise InferenceUnavailableError(
                f"inference unavailable: OpenAI-compatible request failed ({exc})"
            ) from exc
        if not isinstance(output_text, str):
            raise InferenceUnavailableError(
                "inference unavailable: the server returned no structured response text"
            )
        return output_schema.model_validate_json(output_text)

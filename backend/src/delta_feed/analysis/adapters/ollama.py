"""Direct local Ollama adapter; no cloud fallback is provided."""

import os
from typing import TypeVar

import requests
from django.conf import settings
from pydantic import BaseModel

from delta_feed.analysis.contracts.extraction import ExtractionResult
from delta_feed.analysis.providers import InferenceUnavailableError

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class OllamaLanguageModel:
    def __init__(
        self,
        *,
        host: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.host = host if host is not None else os.environ.get("OLLAMA_HOST")
        self.model = model if model is not None else os.environ.get("OLLAMA_MODEL")
        self.timeout = timeout if timeout is not None else settings.ANALYSIS_TIMEOUT_SECONDS

    @property
    def model_version(self) -> str:
        return f"ollama:{self.model}" if self.model else "ollama:unconfigured"

    def is_configured(self) -> bool:
        return bool(self.host and self.model)

    def analyze(
        self,
        prompt: str,
        output_schema: type[OutputModel] = ExtractionResult,
    ) -> OutputModel:
        if not self.host:
            raise InferenceUnavailableError(
                "inference unavailable: OLLAMA_HOST is not configured"
            )
        if not self.model:
            raise InferenceUnavailableError(
                "inference unavailable: OLLAMA_MODEL is not configured"
            )
        try:
            host = self.host.rstrip("/")
            if "://" not in host:
                host = f"http://{host}"
            response = requests.post(
                f"{host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": output_schema.model_json_schema(),
                    # Extraction should be repeatable, not creative.
                    "options": {"temperature": 0},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            output_text = response.json()["response"]
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise InferenceUnavailableError(
                f"inference unavailable: local Ollama request failed ({exc})"
            ) from exc
        if not isinstance(output_text, str):
            raise InferenceUnavailableError(
                "inference unavailable: Ollama returned no structured response text"
            )
        return output_schema.model_validate_json(output_text)

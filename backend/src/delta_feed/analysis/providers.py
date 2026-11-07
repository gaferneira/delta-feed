"""Language-model port and the explicitly configured provider registry.

Only the provider named by ``ANALYSIS_PROVIDER`` is ever used; there is no
fallback to another provider, local or cloud.
"""

from importlib import import_module
from typing import Protocol, TypeVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import BaseModel

OutputModel = TypeVar("OutputModel", bound=BaseModel)

PROVIDERS = {
    "ollama": "delta_feed.analysis.adapters.ollama:OllamaLanguageModel",
    "openai_compatible": (
        "delta_feed.analysis.adapters.openai_compatible:OpenAICompatibleLanguageModel"
    ),
}


class InferenceUnavailableError(RuntimeError):
    """Raised when the provider is not configured or cannot be reached."""


class LanguageModel(Protocol):
    @property
    def model_version(self) -> str: ...

    def is_configured(self) -> bool: ...

    def analyze(self, prompt: str, output_schema: type[OutputModel]) -> OutputModel: ...


def configured_language_model() -> LanguageModel:
    name = settings.ANALYSIS_PROVIDER
    if name not in PROVIDERS:
        raise ImproperlyConfigured(f"Unknown ANALYSIS_PROVIDER: {name!r}")
    module_path, class_name = PROVIDERS[name].split(":", 1)
    return getattr(import_module(module_path), class_name)()

import pytest

from delta_feed.analysis.adapters.ollama import (
    InferenceUnavailableError,
    OllamaLanguageModel,
)
from delta_feed.analysis.prompts.extraction import (
    PROMPT_VERSION,
    render_extraction_prompt,
)


def test_extraction_prompt_renders_versioned_placeholders():
    prompt = render_extraction_prompt(article_title="Release notes", article_text="Widget is stable.")

    assert "Release notes" in prompt
    assert "Widget is stable." in prompt
    assert "delta-feed.extraction.v1" in prompt
    assert PROMPT_VERSION in prompt
    assert "{{article_text}}" not in prompt


def test_ollama_adapter_reports_unavailable_without_host(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "local-model")

    with pytest.raises(InferenceUnavailableError, match="inference unavailable"):
        OllamaLanguageModel().analyze("prompt")


def test_ollama_adapter_reports_unavailable_when_local_endpoint_cannot_be_reached(monkeypatch):
    import requests

    def fail_request(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "local-model")
    monkeypatch.setattr(requests, "post", fail_request)

    with pytest.raises(InferenceUnavailableError, match="inference unavailable"):
        OllamaLanguageModel().analyze("prompt")

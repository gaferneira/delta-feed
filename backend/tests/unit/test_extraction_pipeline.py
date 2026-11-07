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


def test_openai_compatible_adapter_requests_the_schema_and_parses_the_reply(monkeypatch):
    import json
    from unittest.mock import Mock

    import requests

    from delta_feed.analysis.adapters.openai_compatible import (
        OpenAICompatibleLanguageModel,
    )
    from delta_feed.analysis.contracts.extraction import (
        EXTRACTION_SCHEMA_ID,
        ExtractionResult,
    )

    reply = {"schema_id": EXTRACTION_SCHEMA_ID, "entities": [], "claims": []}
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": json.dumps(reply)}}]}
    post = Mock(return_value=response)
    monkeypatch.setattr(requests, "post", post)

    model = OpenAICompatibleLanguageModel(
        base_url="http://127.0.0.1:1234/v1/", model="qwen/qwen3.8-27b", api_key="", timeout=5
    )
    result = model.analyze("prompt", ExtractionResult)

    assert result.claims == []
    assert post.call_args.args[0] == "http://127.0.0.1:1234/v1/chat/completions"
    assert post.call_args.kwargs["headers"] == {}
    sent = post.call_args.kwargs["json"]
    assert sent["response_format"]["json_schema"]["name"] == "ExtractionResult"
    assert sent["temperature"] == 0


def test_openai_compatible_adapter_reports_unavailable_without_base_url(monkeypatch):
    from delta_feed.analysis.adapters.openai_compatible import (
        OpenAICompatibleLanguageModel,
    )

    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "local-model")

    with pytest.raises(InferenceUnavailableError, match="inference unavailable"):
        OpenAICompatibleLanguageModel().analyze("prompt")

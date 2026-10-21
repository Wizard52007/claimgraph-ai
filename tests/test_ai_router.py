import pytest

from unittest.mock import patch

from claimgraph.gemini_client import (
    generate_text,
    get_configured_providers,
)
from google.genai import errors


def test_only_configured_providers_are_used(monkeypatch):
    """Providers without API keys must be skipped."""

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    providers = get_configured_providers()

    assert providers
    assert all(provider == "gemini" for provider, _ in providers)


def test_fallback_to_next_model(monkeypatch):
    """A failed model should be followed by the next configured model."""

    import claimgraph.gemini_client as router

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    monkeypatch.setenv(
    "GEMINI_MODELS",
    "gemini-test-first,gemini-test-second",
    )

    def fake_generate(provider, model, prompt):
        if model == "gemini-test-first":
            raise errors.APIError(
               code=503,
               response_json={"error": {"message": "Simulated provider failure"}},
            )

        return "Successful fallback response"

    with patch(
        "claimgraph.gemini_client._generate_with_provider",
        side_effect=fake_generate,
    ) as mocked_generate:

        result = generate_text("Test prompt")

    assert result == "Successful fallback response"
    assert mocked_generate.call_count == 2


def test_all_models_failing_raises_error(monkeypatch):
    """The router should report an error if every model fails."""

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODELS", "gemini-test-failure")

    with patch(
        "claimgraph.gemini_client._generate_with_provider",
        side_effect=errors.APIError(
            code=503,
            response_json={"error": {"message": "Simulated failure"}},
        ),
    ):
        with pytest.raises(RuntimeError, match="All configured AI models failed"):
            generate_text("Test prompt")


def test_no_configured_provider_raises_error(monkeypatch):
    """The router should fail clearly if no provider is configured."""

    for key in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="No AI provider is configured"):
        generate_text("Test prompt")

def test_fallback_between_providers(monkeypatch):
    """The router should switch providers when Gemini fails."""

    import claimgraph.gemini_client as router

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv(
        "GEMINI_MODELS",
        "gemini-test-model",
    )

    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    monkeypatch.setenv("OPENAI_MODELS", "openai-test-model")

    def fake_generate(provider, model, prompt):
        if provider == "gemini":
            raise errors.APIError(
                code=503,
                response_json={"error": {"message": "Simulated Gemini failure"}},
            )

        if provider == "openai":
            return "OpenAI fallback response"

        raise AssertionError(f"Unexpected provider: {provider}")

    with patch(
        "claimgraph.gemini_client._generate_with_provider",
        side_effect=fake_generate,
    ) as mocked_generate:

        result = router.generate_text("Test prompt")

    assert result == "OpenAI fallback response"
    assert mocked_generate.call_count == 2

    assert mocked_generate.call_args_list[0].args[0] == "gemini"
    assert mocked_generate.call_args_list[1].args[0] == "openai"

def test_non_retryable_error_stops_fallback(monkeypatch):
    """Non-retryable errors should stop fallback immediately."""

    import claimgraph.gemini_client as router
    from google.genai import errors

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv(
        "GEMINI_MODELS",
        "gemini-test-first,gemini-test-second",
    )

    with patch(
        "claimgraph.gemini_client._generate_with_provider",
        side_effect=errors.APIError(
            code=400,
            response_json={"error": {"message": "Invalid request"}},
        ),
    ) as mocked_generate:

        with pytest.raises(
            RuntimeError,
            match="AI provider gemini failed",
        ):
            router.generate_text("Test prompt")

    assert mocked_generate.call_count == 1

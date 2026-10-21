import logging
import os
import time

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import errors as google_errors
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def get_models(env_name: str, default: str = "") -> list[str]:
    """Read a comma-separated list of model names from an environment variable."""
    value = os.getenv(env_name, default)

    return [
        model.strip()
        for model in value.split(",")
        if model.strip()
    ]


def get_configured_providers() -> list[tuple[str, str]]:
    """
    Return configured providers in priority order.

    Ollama is opt-in through USE_OLLAMA=true.
    Cloud providers are included only when their API keys are configured.
    """
    providers: list[tuple[str, str]] = []

    # Local Ollama: disabled unless explicitly enabled.
    use_ollama = os.getenv("USE_OLLAMA", "").strip().lower()

    if use_ollama in {"1", "true", "yes"}:
        ollama_models = get_models(
            "OLLAMA_MODELS",
            "gemma4:e4b",
        )
        providers.extend(
            ("ollama", model)
            for model in ollama_models
        )

    # Google Gemini
    if os.getenv("GEMINI_API_KEY"):
        gemini_models = get_models(
            "GEMINI_MODELS",
            "gemini-2.5-flash",
        )
        providers.extend(
            ("gemini", model)
            for model in gemini_models
        )

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        openai_models = get_models(
            "OPENAI_MODELS",
            "gpt-4o-mini",
        )
        providers.extend(
            ("openai", model)
            for model in openai_models
        )

    # Groq
    if os.getenv("GROQ_API_KEY"):
        groq_models = get_models(
            "GROQ_MODELS",
            "llama-3.3-70b-versatile",
        )
        providers.extend(
            ("groq", model)
            for model in groq_models
        )

    # OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        openrouter_models = get_models(
            "OPENROUTER_MODELS",
            "openai/gpt-4o-mini",
        )
        providers.extend(
            ("openrouter", model)
            for model in openrouter_models
        )

    return providers


def _generate_with_provider(
    provider: str,
    model: str,
    prompt: str,
) -> str:
    """Generate text using the specified provider."""

    # Local Ollama
    if provider == "ollama":
        base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434",
        ).rstrip("/")

        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "stream": False,
            },
            timeout=180,
        )

        response.raise_for_status()

        result = response.json()
        content = result.get("message", {}).get("content", "")

        if not content:
            raise RuntimeError(
                f"Ollama returned an empty response for model '{model}'."
            )

        return content

    # Google Gemini
    if provider == "gemini":
        client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"]
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        if not response.text:
            raise RuntimeError(
                f"Gemini returned an empty response for model '{model}'."
            )

        return response.text

    # OpenAI
    if provider == "openai":
        client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"]
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                f"OpenAI returned an empty response for model '{model}'."
            )

        return content

    # Groq
    if provider == "groq":
        client = Groq(
            api_key=os.environ["GROQ_API_KEY"]
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                f"Groq returned an empty response for model '{model}'."
            )

        return content

    # OpenRouter
    if provider == "openrouter":
        client = OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                f"OpenRouter returned an empty response for model '{model}'."
            )

        return content

    raise ValueError(f"Unsupported AI provider: {provider}")


def _get_http_status(exc: Exception) -> int | None:
    """Extract an HTTP status code from a provider exception."""

    status = getattr(exc, "code", None)

    if status is None:
        status = getattr(exc, "status_code", None)

    if status is None:
        response = getattr(exc, "response", None)

        if response is not None:
            status = getattr(response, "status_code", None)

    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _is_retryable_provider_error(exc: Exception) -> bool:
    """
    Return True when trying another model/provider is reasonable.

    Authentication errors, invalid requests, and programming errors
    should not automatically trigger fallback.
    """

    # Google Gemini
    if isinstance(exc, google_errors.APIError):
        return _get_http_status(exc) in RETRYABLE_STATUS_CODES

    # OpenAI-compatible providers
    if isinstance(exc, APIStatusError):
        return _get_http_status(exc) in RETRYABLE_STATUS_CODES

    if isinstance(
        exc,
        (APIConnectionError, APITimeoutError),
    ):
        return True

    # Ollama HTTP/network errors
    if isinstance(
        exc,
        (
            requests.ConnectionError,
            requests.Timeout,
        ),
    ):
        return True

    if isinstance(exc, requests.HTTPError):
        status = _get_http_status(exc)
        return status in RETRYABLE_STATUS_CODES

    return False


def generate_text(prompt: str) -> str:
    """
    Generate text using configured providers in priority order.

    Retryable errors trigger fallback to another model/provider.
    A non-retryable error stops execution immediately.
    """

    providers = get_configured_providers()

    if not providers:
        raise RuntimeError(
            "No AI provider is configured. Enable Ollama with "
            "USE_OLLAMA=true or configure an API key such as "
            "GEMINI_API_KEY."
        )

    attempted_providers: list[str] = []
    skipped_providers: set[str] = set()

    for provider, model in providers:
        if provider in skipped_providers:
            continue

        attempted_providers.append(f"{provider}:{model}")

        try:
            logger.info(
                "Generating text with provider=%s model=%s",
                provider,
                model,
            )

            start_time = time.perf_counter()

            result = _generate_with_provider(
                provider,
                model,
                prompt,
            )

            elapsed = time.perf_counter() - start_time

            logger.info(
              "AI generation completed: provider=%s model=%s duration=%.2fs",
               provider,
               model,
               elapsed,
            )

            logger.info(
                "Generation succeeded with provider=%s model=%s",
                provider,
                model,
            )

            return result

        except Exception as exc:
            status = _get_http_status(exc)

            logger.warning(
                "Provider failed: provider=%s model=%s "
                "error_type=%s status=%s",
                provider,
                model,
                type(exc).__name__,
                status,
            )

            if not _is_retryable_provider_error(exc):
                raise RuntimeError(
                       f"AI provider {provider} failed with model '{model}': {exc}"
                ) from exc

            # If a provider is rate-limited, skip its remaining models.
            if status == 429:
                skipped_providers.add(provider)

            logger.info(
                "Trying the next configured AI model/provider."
            )

    attempted = ", ".join(attempted_providers)

    raise RuntimeError(
        "All configured AI models failed. "
        f"Attempted: {attempted}. "
        "Check provider availability, network connectivity, "
        "API quotas, and configuration."
    )
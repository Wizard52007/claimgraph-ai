import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def get_models(env_name: str, default: str = "") -> list[str]:
    """Read a comma-separated model list from the environment."""
    return [
        model.strip()
        for model in os.getenv(env_name, default).split(",")
        if model.strip()
    ]


def get_configured_providers():
    """Return configured providers in fallback priority order."""
    providers = []

    if os.getenv("GEMINI_API_KEY"):
        providers.extend(
            ("gemini", model)
            for model in get_models(
                "GEMINI_MODELS",
                "gemini-2.5-flash,gemini-3.5-flash,gemini-2.5-pro",
            )
        )

    if os.getenv("OPENAI_API_KEY"):
        providers.extend(
            ("openai", model) for model in get_models("OPENAI_MODELS")
        )

    if os.getenv("GROQ_API_KEY"):
        providers.extend(
            ("groq", model) for model in get_models("GROQ_MODELS")
        )

    if os.getenv("OPENROUTER_API_KEY"):
        providers.extend(
            ("openrouter", model)
            for model in get_models("OPENROUTER_MODELS")
        )

    return providers


def _generate_with_provider(provider, model, prompt):
    """Send a prompt to one configured provider."""
    if provider == "gemini":
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        result = response.text

    elif provider == "openai":
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.choices[0].message.content

    elif provider == "groq":
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.choices[0].message.content

    elif provider == "openrouter":
        client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.choices[0].message.content

    else:
        raise ValueError(f"Unsupported AI provider: {provider}")

    if not result or not result.strip():
        raise RuntimeError(
            f"{provider} model {model} returned an empty response."
        )

    return result.strip()


def _get_http_status(exc):
    """Extract an HTTP status when the SDK exposes one."""
    status = getattr(exc, "code", None)

    if status is None:
        status = getattr(exc, "status_code", None)

    return status if isinstance(status, int) else None


def _is_retryable_provider_error(exc):
    """Determine whether another model/provider should be attempted."""
    if isinstance(exc, errors.APIError):
        status = _get_http_status(exc)
        return status in RETRYABLE_STATUS_CODES

    if isinstance(exc, APIStatusError):
        return exc.status_code in RETRYABLE_STATUS_CODES

    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True

    # Do not silently retry arbitrary programming/configuration errors.
    return False


def generate_text(prompt: str) -> str:
    """Generate text using ordered models and automatic provider fallback."""
    providers = get_configured_providers()

    if not providers:
        raise RuntimeError(
            "No AI provider is configured. Set GEMINI_API_KEY "
            "or configure another provider and its model list."
        )

    failures = []

    for provider, model in providers:
        try:
            logger.info(
                "Trying AI provider %s with model %s",
                provider,
                model,
            )

            result = _generate_with_provider(provider, model, prompt)

            logger.info(
                "AI generation succeeded with %s / %s",
                provider,
                model,
            )

            return result

        except Exception as exc:
            status = _get_http_status(exc)
            retryable = _is_retryable_provider_error(exc)

            # Log only non-sensitive metadata, not the raw exception.
            logger.warning(
                "Provider %s model %s failed: error_type=%s status=%s retryable=%s",
                provider,
                model,
                type(exc).__name__,
                status,
                retryable,
            )

            if status is not None:
                failures.append(
                    f"{provider}/{model}: HTTP {status}"
                )
            else:
                failures.append(
                    f"{provider}/{model}: {type(exc).__name__}"
                )

            if not retryable:
                # Configuration and programming errors should not be hidden.
                raise RuntimeError(
                    f"AI provider {provider} failed with "
                    f"{type(exc).__name__}."
                ) from exc

            # Move to the next configured model/provider after a
            # retryable outage, timeout, or rate-limit response.

    details = "; ".join(failures)

    logger.error("All configured AI models failed: %s", details)

    raise RuntimeError(
        "All configured AI models failed. "
        f"Failures: {details}"
    )
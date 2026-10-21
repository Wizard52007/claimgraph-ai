import os
import time
import logging

from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.8-flash"

MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2


def get_gemini_client() -> genai.Client:
    """Create a Gemini client using the configured API key."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Add it to your local .env file."
        )

    return genai.Client(api_key=api_key)


def generate_text(prompt: str) -> str:
    """Generate text using Gemini with retries for temporary failures."""
    client = get_gemini_client()

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            if not response.text:
                raise RuntimeError("Gemini returned an empty response.")

            return response.text.strip()

        except errors.APIError as exc:

            logger.warning(
                "Application caught Gemini API error: HTTP %s",
                exc.code,
            )
            # Retry temporary server errors and rate limits.
            if exc.code not in (429, 500, 502, 503, 504):
                raise

            if attempt == MAX_RETRIES:
                logger.error(
                    "Gemini request failed after %s retries: %s",
                    MAX_RETRIES,
                    exc,
                )
                raise

            delay = INITIAL_RETRY_DELAY * (2 ** attempt)

            logger.warning(
                "Gemini returned HTTP %s. Retrying in %s seconds "
                "(attempt %s/%s).",
                exc.code,
                delay,
                attempt + 1,
                MAX_RETRIES,
            )

            time.sleep(delay)

    raise RuntimeError("Gemini request failed unexpectedly.")
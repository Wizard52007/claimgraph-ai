import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL_NAME = "gemini-3.8-flash"


def get_gemini_client() -> genai.Client:
    """Create a Gemini client using the configured API key."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Add it to your local .env file."
        )

    return genai.Client(api_key=api_key)


def generate_text(prompt: str) -> str:
    """Generate text using Gemini."""
    client = get_gemini_client()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return response.text.strip()
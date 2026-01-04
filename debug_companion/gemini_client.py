import os
from typing import Any, Dict, Optional

try:
    from google import genai  # pip install google-genai
except ImportError:  # pragma: no cover
    genai = None


def get_gemini_client(logger) -> Optional[Any]:
    if genai is None:
        return None

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning("Failed to init Gemini client: %s", e)
        return None


def analyze_error_with_gemini_impl(
    *,
    logger,
    error_message: str,
    code_context: str,
) -> Dict[str, Any]:
    client = get_gemini_client(logger)
    if client is None:
        return {"ok": False, "error": "Gemini API Key not configured or client init failed"}

    model_name = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()

    prompt = f"""
I have a Python test failure.

Error message:
{error_message}

Code context:
{code_context}

Please explain why this error is happening and suggest a fix.
""".strip()

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return {"ok": True, "analysis": response.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

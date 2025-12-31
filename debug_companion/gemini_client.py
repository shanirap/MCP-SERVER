import os
from typing import Any, Dict, Optional


def get_gemini_model(genai_module, logger) -> Optional[Any]:
    if genai_module is None:
        return None

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None

    try:
        genai_module.configure(api_key=api_key)
        return genai_module.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning("Failed to init Gemini model: %s", e)
        return None


def analyze_error_with_gemini_impl(
    *,
    genai_module,
    logger,
    error_message: str,
    code_context: str,
) -> Dict[str, Any]:
    model = get_gemini_model(genai_module, logger)
    if model is None:
        return {"ok": False, "error": "Gemini API Key not configured or model init failed"}

    prompt = f"""
I have a Python test failure.

Error message:
{error_message}

Code context:
{code_context}

Please explain why this error is happening and suggest a fix.
""".strip()

    try:
        response = model.generate_content(prompt)
        return {"ok": True, "analysis": getattr(response, "text", str(response))}
    except Exception as e:
        return {"ok": False, "error": str(e)}

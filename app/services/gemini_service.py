"""
app/services/gemini_service.py
-------------------------------
Low-level wrapper around the Google Gen AI Python SDK (google-genai).

Responsibilities:
- Initialise the Gemini client once at startup
- Expose a typed generate() helper with retry logic (tenacity)
- Expose a function-calling-aware chat() method used by the agent loop
- Model switching is controlled entirely via the GEMINI_MODEL env var

Why Gemini?
- Native function calling (tool use) enables true agentic ReAct loops
- Gemini 2.0 Flash is fast and cost-efficient for real-time productivity apps
- Long context window handles task lists + conversation history easily
- Google AI Studio provides one-click Cloud Run deployment
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import retry_if_exception, stop_after_attempt

from app.config import get_settings
from app.utils.logging_config import get_logger


def _is_retryable_429(exc: BaseException) -> bool:
    """
    Return True only for per-minute rate limits (retryable).
    Daily quota exhaustion (limit: 0) is not retryable — fail fast.
    """
    if not isinstance(exc, genai_errors.ClientError):
        return True  # retry other errors normally
    if exc.code != 429:
        return True
    # Daily quota exhausted when the limit value is 0
    msg = str(exc)
    if "limit: 0" in msg and "PerDay" in msg:
        return False  # don't retry daily exhaustion
    return True  # per-minute throttle — retryable


def _retry_wait(exc: BaseException) -> float:
    """Parse retryDelay from Gemini 429 response; default to 65s."""
    try:
        msg = str(exc)
        m = re.search(r"retryDelay.*?(\d+)s", msg)
        return float(m.group(1)) + 5 if m else 65.0
    except Exception:
        return 65.0

logger = get_logger(__name__)
settings = get_settings()


def _init_gemini() -> genai.Client:
    """Create and return the Gemini client configured from environment."""
    client = genai.Client(api_key=settings.gemini_api_key)
    logger.info("Gemini SDK initialised with model: %s", settings.gemini_model)
    return client


# Module-level client – created once on import
_client = _init_gemini()


def _base_config(**overrides: Any) -> types.GenerateContentConfig:
    """Return a GenerateContentConfig built from environment settings."""
    return types.GenerateContentConfig(
        temperature=settings.agent_temperature,
        max_output_tokens=settings.agent_max_output_tokens,
        **overrides,
    )


def _gemini_retry():
    """Shared retry decorator for all Gemini calls."""
    from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential, before_sleep_log
    import logging

    def _wait(retry_state):
        exc = retry_state.outcome.exception()
        if isinstance(exc, genai_errors.ClientError) and exc.code == 429:
            secs = _retry_wait(exc)
            logger.warning("Gemini 429 – waiting %.0fs before retry", secs)
            return secs
        # Exponential back-off for other transient errors
        return min(2 ** retry_state.attempt_number, 30)

    return retry(
        retry=retry_if_exception(_is_retryable_429),
        stop=stop_after_attempt(3),
        wait=_wait,
        reraise=True,
    )


@_gemini_retry()
def generate_text(prompt: str, system_instruction: Optional[str] = None) -> str:
    """
    Simple single-turn text generation with retry logic.
    Used for straightforward AI tasks (summaries, categorisation, etc.).

    Args:
        prompt: The user prompt
        system_instruction: Optional system-level instruction for the model

    Returns:
        The model's text response
    """
    config = _base_config(
        system_instruction=system_instruction,
        response_mime_type="text/plain",
    )
    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=config,
    )
    text = response.text.strip()
    logger.debug("generate_text → %d chars", len(text))
    return text


@_gemini_retry()
def generate_json(prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate structured JSON output from Gemini.
    Forces JSON response mime type.

    Returns:
        Parsed dict from the model response
    """
    config = _base_config(
        system_instruction=system_instruction,
        response_mime_type="application/json",
    )
    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=config,
    )
    raw = response.text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: strip markdown code fences if present
        cleaned = raw.strip("```json").strip("```").strip()
        return json.loads(cleaned)


class GeminiAgentSession:
    """
    Stateful multi-turn chat session with Gemini function calling.
    One instance per agent conversation thread.

    The session maintains conversation history so the model retains
    context across multiple turns (multi-step agentic reasoning).
    """

    def __init__(
        self,
        system_instruction: str,
        tools: Optional[List[Any]] = None,
    ) -> None:
        config = _base_config(
            system_instruction=system_instruction,
            tools=tools or [],
            # Disable Automatic Function Calling — we run our own ReAct loop
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        self._chat = _client.chats.create(
            model=settings.gemini_model,
            config=config,
        )
        logger.debug("GeminiAgentSession created with model=%s", settings.gemini_model)

    @_gemini_retry()
    def send_message(self, message: Any) -> Any:
        """
        Send a message (string or Part) and return the raw Gemini response.
        The caller (agent loop) inspects the response for function calls.
        """
        response = self._chat.send_message(message)
        return response

    def send_tool_result(self, tool_name: str, result: Any) -> Any:
        """
        Feed a tool execution result back to the model.
        This is the 'Act → Observe' step in the ReAct loop.
        """
        part = types.Part.from_function_response(
            name=tool_name,
            response={"result": result},
        )
        return self._chat.send_message(part)

    @property
    def history(self) -> List[Any]:
        """Return the conversation history for persistence / debugging."""
        return self._chat.get_history()
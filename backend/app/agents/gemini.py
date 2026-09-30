"""Gemini Flash client with JSON function-calling (CLAUDE.MD §5, §10).

Uses models.generate_content, not the newer interactions endpoint. That was a
deliberate change after testing: on a free-tier 429 the interactions endpoint
HANGS rather than returning the error, while generate_content surfaces it in
under a second. A hang mid-call is indistinguishable on screen from the product
being dead, and the free tier's normal failure mode is exactly that 429
(PLAN.md open risks).

Conversation history is carried explicitly in a contents list. Verified against
google-genai 2.25.0 by introspection and live calls, not from memory.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from app.config import Settings

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolCall:
    name: str
    args: dict[str, Any]
    ms: int = 0


class GeminiUnavailable(RuntimeError):
    """Raised once retries are exhausted, so callers degrade instead of hang."""


class GeminiAgent:
    """One conversation with one system prompt and one tool set."""

    def __init__(
        self,
        settings: Settings,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._tool = types.Tool(function_declarations=tools)
        self._system = system_prompt
        self._history: list[types.Content] = []
        self._calls_made = 0

    @property
    def calls_made(self) -> int:
        return self._calls_made

    def _config(self, force_tool: bool) -> types.GenerateContentConfig:
        cfg: dict[str, Any] = {
            "system_instruction": self._system,
            "tools": [self._tool],
            # Low temperature on purpose: this is extraction, not writing. A
            # creative model invents a district it was never told.
            "temperature": 0.2,
        }
        if force_tool:
            # ANY guarantees a tool call instead of a sympathetic paragraph.
            cfg["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        return types.GenerateContentConfig(**cfg)

    async def turn(
        self, text: str, *, force_tool: bool = False
    ) -> tuple[str, list[ToolCall]]:
        """Send one user turn. Returns (spoken reply, tool calls requested)."""
        self._history.append(
            types.Content(role="user", parts=[types.Part(text=text)])
        )
        response = await self._generate(force_tool)
        return self._absorb(response)

    def _absorb(self, response: Any) -> tuple[str, list[ToolCall]]:
        """Record the model's turn in history and split it into text + calls."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "", []
        content = candidates[0].content
        if content is not None:
            self._history.append(content)

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc is not None and fc.name:
                calls.append(ToolCall(name=fc.name, args=dict(fc.args or {})))
        return " ".join(text_parts).strip(), calls

    async def _generate(self, force_tool: bool) -> Any:
        """One API call, with backoff on transient failures.

        Delays are short by design. A victim is mid-sentence; a 30-second
        backoff is indistinguishable from the product being broken.
        """
        if self._calls_made >= self._settings.gemini_max_calls_per_session:
            raise GeminiUnavailable(
                f"Gemini call budget reached "
                f"({self._settings.gemini_max_calls_per_session} per session)"
            )

        delays = (0.5, 1.5, 3.0)
        last: Exception | None = None
        for attempt, delay in enumerate((0.0, *delays)):
            if delay:
                await asyncio.sleep(delay)
            try:
                self._calls_made += 1
                started = time.monotonic()
                result = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=self._settings.gemini_model,
                        contents=self._history,
                        config=self._config(force_tool),
                    ),
                    timeout=self._settings.gemini_timeout_seconds,
                )
                log.info(
                    "gemini call %d in %.0fms",
                    self._calls_made,
                    (time.monotonic() - started) * 1000,
                )
                return result
            except asyncio.TimeoutError as exc:
                last = exc
                log.warning("gemini attempt %d timed out", attempt + 1)
            except Exception as exc:
                last = exc
                if not _retryable(exc):
                    raise GeminiUnavailable(_explain(exc)) from exc
                log.warning("gemini attempt %d failed: %s", attempt + 1, exc)
        raise GeminiUnavailable(_explain(last) if last else "Gemini unavailable")


def _retryable(exc: Exception) -> bool:
    """429 and 5xx are worth another try; a bad request or bad key is not.

    A daily-quota 429 is NOT worth retrying — it will not clear for hours, and
    three retries only burn the demo's remaining seconds.
    """
    text = str(exc).lower()
    if "perday" in text.replace("_", "").replace("-", ""):
        return False
    if any(s in text for s in ("429", "resource_exhausted", "rate limit", "quota")):
        return True
    return any(s in text for s in ("500", "502", "503", "504", "unavailable"))


def _explain(exc: Exception) -> str:
    """Turn a provider error into something a person can act on."""
    text = str(exc)
    lowered = text.replace("_", "").replace("-", "").lower()
    if "perday" in lowered:
        return (
            "Gemini free-tier daily quota exhausted for this model. It resets "
            "tomorrow, or switch GEMINI_MODEL to another Flash model — the "
            "daily limit is per model."
        )
    if "429" in text or "resource_exhausted" in text.lower():
        return "Gemini rate limit hit. Retrying did not clear it."
    if "api key" in text.lower() or "401" in text or "403" in text:
        return "Gemini rejected the API key."
    return text[:300]

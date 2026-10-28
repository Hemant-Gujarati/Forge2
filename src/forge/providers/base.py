"""Base provider and stream event types for Forge."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator

import httpx


@dataclass
class ToolCall:
    """Represents a tool call from the AI."""

    id: str
    name: str
    arguments: dict


@dataclass
class TextDelta:
    """A chunk of streamed text."""

    text: str


@dataclass
class ToolCallEvent:
    """A completed tool call to execute."""

    tool_call: ToolCall


@dataclass
class ErrorEvent:
    """An error from the provider."""

    message: str


@dataclass
class DoneEvent:
    """Signals the end of streaming."""

    pass


# Union type for stream events
StreamEvent = TextDelta | ToolCallEvent | ErrorEvent | DoneEvent


def parse_sse_line(line: str) -> tuple[str | None, str | None]:
    """Parse a single SSE line, returning (field, value)."""
    if line.startswith("data: "):
        return "data", line[6:]
    elif line.startswith("event: "):
        return "event", line[7:]
    elif line.startswith(":"):
        return "comment", line[1:]
    return None, None


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("default_model", "")
        self.base_url = config.get("base_url", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self.client = httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
        )

    def set_model(self, model: str):
        """Switch to a different model."""
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """
        Send messages to the model and yield stream events.

        Messages use the common format:
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "...", "tool_calls": [{"id":..., "name":..., "arguments":...}]},
            {"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."},
        ]

        Tools use the common format:
        [
            {"name": "...", "description": "...", "parameters": {...json_schema...}}
        ]
        """
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models for this provider."""
        ...

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass

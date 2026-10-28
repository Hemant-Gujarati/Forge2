"""Ollama local model provider for Forge."""

import json
import uuid
from typing import Generator

import httpx

from forge.providers.base import (
    BaseProvider, StreamEvent, TextDelta, ToolCallEvent,
    ToolCall, ErrorEvent, DoneEvent,
)


class OllamaProvider(BaseProvider):
    """Provider for local models via Ollama."""

    name = "ollama"

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.base_url:
            self.base_url = "http://localhost:11434"

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """Convert common tool format to Ollama/OpenAI format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

    def _format_messages(self, messages: list[dict]) -> list[dict]:
        """Convert common message format to Ollama format."""
        formatted = []
        for msg in messages:
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                tool_calls = []
                for tc in msg["tool_calls"]:
                    tool_calls.append({
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        }
                    })
                formatted.append({
                    "role": "assistant",
                    "content": msg.get("content", ""),
                    "tool_calls": tool_calls,
                })
            elif msg["role"] == "tool":
                formatted.append({
                    "role": "tool",
                    "content": msg["content"],
                })
            else:
                formatted.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
        return formatted

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Stream chat from Ollama."""
        body: dict = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "stream": True,
        }
        if tools:
            body["tools"] = self._format_tools(tools)

        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=body,
            ) as response:
                if response.status_code != 200:
                    error_body = response.read().decode()
                    yield ErrorEvent(f"Ollama error {response.status_code}: {error_body[:500]}")
                    yield DoneEvent()
                    return

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = chunk.get("message", {})

                    # Text content
                    content = message.get("content", "")
                    if content:
                        yield TextDelta(content)

                    # Tool calls (come with done=true or in message)
                    if message.get("tool_calls"):
                        for tc in message["tool_calls"]:
                            func = tc.get("function", {})
                            args = func.get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    args = {"_raw": args}
                            yield ToolCallEvent(ToolCall(
                                id=f"ollama_{uuid.uuid4().hex[:8]}",
                                name=func.get("name", ""),
                                arguments=args,
                            ))

                    if chunk.get("done", False):
                        break

        except httpx.ConnectError:
            yield ErrorEvent(
                "Cannot connect to Ollama. Is it running?\n"
                "Start it with: ollama serve\n"
                "Install from: https://ollama.com"
            )
        except Exception as e:
            yield ErrorEvent(f"Ollama request failed: {type(e).__name__}: {e}")

        yield DoneEvent()

    def list_models(self) -> list[str]:
        """List locally available Ollama models."""
        try:
            resp = self.client.get(f"{self.base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return sorted(models) if models else ["(no models installed — run: ollama pull llama3.2)"]
            return [f"(Error: {resp.status_code})"]
        except httpx.ConnectError:
            return ["(Ollama not running — start with: ollama serve)"]
        except Exception as e:
            return [f"(Error: {e})"]

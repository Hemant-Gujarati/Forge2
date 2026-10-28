"""OpenAI-compatible provider for Forge."""

import json
import uuid
from typing import Generator

from forge.providers.base import (
    BaseProvider, StreamEvent, TextDelta, ToolCallEvent,
    ToolCall, ErrorEvent, DoneEvent, parse_sse_line,
)


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI and any OpenAI-compatible API."""

    name = "openai"

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """Convert common tool format to OpenAI format."""
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
        """Convert common message format to OpenAI format."""
        formatted = []
        for msg in messages:
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                tool_calls = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in msg["tool_calls"]
                ]
                formatted.append({
                    "role": "assistant",
                    "content": msg.get("content") or None,
                    "tool_calls": tool_calls,
                })
            elif msg["role"] == "tool":
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
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
        """Stream chat completion from OpenAI."""
        body: dict = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "stream": True,
        }
        if tools:
            body["tools"] = self._format_tools(tools)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    error_body = response.read().decode()
                    yield ErrorEvent(f"OpenAI API error {response.status_code}: {error_body[:500]}")
                    yield DoneEvent()
                    return

                # Accumulators for streamed tool calls
                tool_call_accum: dict[int, dict] = {}

                for line in response.iter_lines():
                    if not line:
                        continue
                    field, value = parse_sse_line(line)
                    if field != "data" or value is None:
                        continue
                    if value.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(value)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish = choices[0].get("finish_reason")

                    # Text content
                    if delta.get("content"):
                        yield TextDelta(delta["content"])

                    # Tool calls (streamed incrementally)
                    if delta.get("tool_calls"):
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_call_accum:
                                tool_call_accum[idx] = {
                                    "id": tc_delta.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc_delta.get("id"):
                                tool_call_accum[idx]["id"] = tc_delta["id"]
                            func = tc_delta.get("function", {})
                            if func.get("name"):
                                tool_call_accum[idx]["name"] = func["name"]
                            if func.get("arguments"):
                                tool_call_accum[idx]["arguments"] += func["arguments"]

                # Emit accumulated tool calls
                for idx in sorted(tool_call_accum.keys()):
                    tc = tool_call_accum[idx]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {"_raw": tc["arguments"]}
                    yield ToolCallEvent(ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=args,
                    ))

        except Exception as e:
            yield ErrorEvent(f"OpenAI request failed: {type(e).__name__}: {e}")

        yield DoneEvent()

    def list_models(self) -> list[str]:
        """List available OpenAI models."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = self.client.get(f"{self.base_url}/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return sorted(models)
            return [f"(Error listing models: {resp.status_code})"]
        except Exception as e:
            return [f"(Error: {e})"]

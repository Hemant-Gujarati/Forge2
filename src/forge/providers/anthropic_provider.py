"""Anthropic Claude provider for Forge."""

import json
import uuid
from typing import Generator

from forge.providers.base import (
    BaseProvider,
    DoneEvent,
    ErrorEvent,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    parse_sse_line,
)


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models."""

    name = "anthropic"

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """Convert common tool format to Anthropic format."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]

    def _format_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Convert common messages to Anthropic format. Returns (system_prompt, messages)."""
        system_parts = []
        formatted = []

        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "user":
                formatted.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": tc["arguments"],
                            }
                        )
                if content_blocks:
                    formatted.append({"role": "assistant", "content": content_blocks})
            elif msg["role"] == "tool":
                # Tool results must be user messages with tool_result blocks
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg["tool_call_id"],
                    "content": msg["content"],
                }
                # Merge consecutive tool results into one user message
                if (
                    formatted
                    and formatted[-1]["role"] == "user"
                    and isinstance(formatted[-1]["content"], list)
                ):
                    formatted[-1]["content"].append(tool_result)
                else:
                    formatted.append({"role": "user", "content": [tool_result]})

        system = "\n\n".join(system_parts) if system_parts else ""
        return system, formatted

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Stream chat completion from Anthropic."""
        system, fmt_messages = self._format_messages(messages)

        body: dict = {
            "model": self.model,
            "messages": fmt_messages,
            "max_tokens": 8192,
            "stream": True,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = self._format_tools(tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                json=body,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    error_body = response.read().decode()
                    yield ErrorEvent(
                        f"Anthropic API error {response.status_code}: {error_body[:500]}"
                    )
                    yield DoneEvent()
                    return

                # Track current content block for tool_use accumulation
                current_block_type: str | None = None
                current_tool_id: str = ""
                current_tool_name: str = ""
                current_tool_json: str = ""

                for line in response.iter_lines():
                    if not line:
                        continue
                    field, value = parse_sse_line(line)
                    if field != "data" or value is None:
                        continue

                    try:
                        event = json.loads(value)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        current_block_type = block.get("type")
                        if current_block_type == "tool_use":
                            current_tool_id = block.get("id", f"toolu_{uuid.uuid4().hex[:8]}")
                            current_tool_name = block.get("name", "")
                            current_tool_json = ""

                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield TextDelta(text)

                        elif delta_type == "input_json_delta":
                            current_tool_json += delta.get("partial_json", "")

                    elif event_type == "content_block_stop":
                        if current_block_type == "tool_use":
                            try:
                                args = json.loads(current_tool_json) if current_tool_json else {}
                            except json.JSONDecodeError:
                                args = {"_raw": current_tool_json}
                            yield ToolCallEvent(
                                ToolCall(
                                    id=current_tool_id,
                                    name=current_tool_name,
                                    arguments=args,
                                )
                            )
                        current_block_type = None

                    elif event_type == "message_stop":
                        break

        except Exception as e:
            yield ErrorEvent(f"Anthropic request failed: {type(e).__name__}: {e}")

        yield DoneEvent()

    def list_models(self) -> list[str]:
        """List available Anthropic models."""
        return [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-haiku-3-20250414",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]

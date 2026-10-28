"""Google Gemini provider for Forge."""

import json
import uuid
from typing import Generator

from forge.providers.base import (
    BaseProvider, StreamEvent, TextDelta, ToolCallEvent,
    ToolCall, ErrorEvent, DoneEvent, parse_sse_line,
)


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini models."""

    name = "gemini"

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """Convert common tool format to Gemini format."""
        declarations = []
        for t in tools:
            decl = {
                "name": t["name"],
                "description": t["description"],
            }
            # Gemini doesn't accept "required" at the top of parameters in the same way
            params = dict(t["parameters"])
            if params:
                decl["parameters"] = params
            declarations.append(decl)
        return [{"functionDeclarations": declarations}]

    def _format_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Convert common messages to Gemini format. Returns (system_text, contents)."""
        system_parts = []
        contents = []

        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}],
                })
            elif msg["role"] == "assistant":
                parts = []
                if msg.get("content"):
                    parts.append({"text": msg["content"]})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        parts.append({
                            "functionCall": {
                                "name": tc["name"],
                                "args": tc["arguments"],
                            }
                        })
                if parts:
                    contents.append({"role": "model", "parts": parts})
            elif msg["role"] == "tool":
                # Function responses go as user role
                part = {
                    "functionResponse": {
                        "name": msg.get("name", "unknown"),
                        "response": {"result": msg["content"]},
                    }
                }
                # Merge consecutive function responses
                if contents and contents[-1]["role"] == "user" and any(
                    "functionResponse" in p for p in contents[-1]["parts"]
                ):
                    contents[-1]["parts"].append(part)
                else:
                    contents.append({"role": "user", "parts": [part]})

        system = "\n\n".join(system_parts) if system_parts else ""
        return system, contents

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Stream chat from Gemini."""
        system, contents = self._format_messages(messages)

        body: dict = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = self._format_tools(tools)

        # Gemini generation config
        body["generationConfig"] = {
            "maxOutputTokens": 8192,
        }

        url = f"{self.base_url}/models/{self.model}:streamGenerateContent"
        params = {"alt": "sse", "key": self.api_key}

        try:
            with self.client.stream(
                "POST", url, json=body, params=params,
            ) as response:
                if response.status_code != 200:
                    error_body = response.read().decode()
                    yield ErrorEvent(f"Gemini API error {response.status_code}: {error_body[:500]}")
                    yield DoneEvent()
                    return

                for line in response.iter_lines():
                    if not line:
                        continue
                    field, value = parse_sse_line(line)
                    if field != "data" or value is None:
                        continue

                    try:
                        chunk = json.loads(value)
                    except json.JSONDecodeError:
                        continue

                    candidates = chunk.get("candidates", [])
                    if not candidates:
                        continue

                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])

                    for part in parts:
                        if "text" in part:
                            yield TextDelta(part["text"])
                        elif "functionCall" in part:
                            fc = part["functionCall"]
                            yield ToolCallEvent(ToolCall(
                                id=f"gemini_{uuid.uuid4().hex[:8]}",
                                name=fc.get("name", ""),
                                arguments=fc.get("args", {}),
                            ))

        except Exception as e:
            yield ErrorEvent(f"Gemini request failed: {type(e).__name__}: {e}")

        yield DoneEvent()

    def list_models(self) -> list[str]:
        """List available Gemini models."""
        try:
            resp = self.client.get(
                f"{self.base_url}/models",
                params={"key": self.api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    if name.startswith("models/"):
                        name = name[7:]
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        models.append(name)
                return sorted(models)
            return [f"(Error listing models: {resp.status_code})"]
        except Exception as e:
            return [f"(Error: {e})"]

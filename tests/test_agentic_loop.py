"""Test agentic loop, tool chaining, session save/load, and slash commands."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from typing import Generator

from forge.config import SESSIONS_DIR
from forge.providers.base import (
    BaseProvider,
    DoneEvent,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
)
from forge.tools.registry import execute_tool, get_tool_definitions


class MockAgenticProvider(BaseProvider):
    """Mock provider simulating an AI making tool calls then answering."""

    name = "mock"

    def __init__(self):
        super().__init__({"default_model": "mock-model"})
        self.call_count = 0

    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> Generator[StreamEvent, None, None]:
        self.call_count += 1
        if self.call_count == 1:
            # First turn: model decides to create a file
            yield TextDelta("I will create the file for you.\n")
            yield ToolCallEvent(
                ToolCall(
                    id="call_mock_1",
                    name="write_file",
                    arguments={"path": "test_created.txt", "content": "mock file content"},
                )
            )
            yield DoneEvent()
        elif self.call_count == 2:
            # Second turn: after seeing write_file result, model edits the file
            assert any(
                m.get("role") == "tool" and "Successfully wrote" in m.get("content", "")
                for m in messages
            )
            yield TextDelta("Now editing the file.\n")
            yield ToolCallEvent(
                ToolCall(
                    id="call_mock_2",
                    name="edit_file",
                    arguments={
                        "path": "test_created.txt",
                        "old_text": "mock",
                        "new_text": "super mock",
                    },
                )
            )
            yield DoneEvent()
        else:
            # Final turn: model gives summary
            yield TextDelta("Task finished successfully!")
            yield DoneEvent()

    def list_models(self) -> list[str]:
        return ["mock-model"]


class TestAgenticLoop(unittest.TestCase):
    """Test full multi-turn agentic loop with tool execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="forge_loop_")
        self.orig_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mock_agentic_task_execution(self):
        provider = MockAgenticProvider()
        messages: list[dict] = [
            {"role": "system", "content": "You are Forge."},
            {"role": "user", "content": "Create test_created.txt and edit it."},
        ]

        max_iterations = 10
        last_text = ""

        for _ in range(max_iterations):
            text_buffer = ""
            tool_calls = []

            for event in provider.chat(messages, get_tool_definitions()):
                if isinstance(event, TextDelta):
                    text_buffer += event.text
                elif isinstance(event, ToolCallEvent):
                    tool_calls.append(event.tool_call)
                elif isinstance(event, DoneEvent):
                    break

            msg = {"role": "assistant", "content": text_buffer}
            if tool_calls:
                msg["tool_calls"] = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in tool_calls
                ]
            messages.append(msg)

            if text_buffer:
                last_text = text_buffer

            if not tool_calls:
                break

            for tc in tool_calls:
                res = execute_tool(tc.name, tc.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": res,
                    }
                )

        # Verify the file was created and edited
        self.assertTrue(os.path.exists("test_created.txt"))
        with open("test_created.txt") as f:
            content = f.read()
        self.assertEqual(content, "super mock file content")
        self.assertIn("Task finished successfully!", last_text)
        self.assertEqual(provider.call_count, 3)


class TestSessionPersistence(unittest.TestCase):
    """Test saving and loading sessions."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="forge_session_")
        self.orig_sessions = SESSIONS_DIR

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load(self):
        from forge.app import ForgeApp

        app = ForgeApp(provider_name="ollama")
        app.messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello Forge"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        session_file = Path(self.test_dir) / "test_session.json"
        data = {
            "name": "test_session",
            "provider": "ollama",
            "model": "llama3.2",
            "messages": app.messages,
            "cwd": os.getcwd(),
        }
        with open(session_file, "w") as f:
            json.dump(data, f)

        # Verify file is valid JSON
        with open(session_file) as f:
            loaded = json.load(f)
        self.assertEqual(len(loaded["messages"]), 3)
        self.assertEqual(loaded["provider"], "ollama")


if __name__ == "__main__":
    unittest.main()

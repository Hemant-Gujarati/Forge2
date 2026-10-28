"""Comprehensive test suite for Forge CLI."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest

from forge.config import Config
from forge.providers.anthropic_provider import AnthropicProvider
from forge.providers.gemini_provider import GeminiProvider
from forge.providers.ollama_provider import OllamaProvider
from forge.providers.openai_provider import OpenAIProvider
from forge.server.api import create_app
from forge.server.whatsapp import TelegramHandler
from forge.tools.file_tools import (
    delete_file,
    edit_file,
    find_files,
    list_directory,
    read_file,
    search_text,
    write_file,
)
from forge.tools.git_tools import git_status
from forge.tools.registry import execute_tool, get_tool_definitions
from forge.tools.shell_tools import run_command


class TestFileTools(unittest.TestCase):
    """Test all file manipulation tools."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="forge_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_and_read_file(self):
        file_path = os.path.join(self.test_dir, "nested", "test.py")
        content = "print('Hello, Forge!')\n"
        result = write_file(file_path, content)
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.exists(file_path))

        read_content = read_file(file_path)
        self.assertEqual(read_content, content)

    def test_edit_file(self):
        file_path = os.path.join(self.test_dir, "edit_test.txt")
        write_file(file_path, "apple\nbanana\ncherry\n")
        result = edit_file(file_path, "banana", "blueberry")
        self.assertIn("Successfully replaced", result)
        self.assertEqual(read_file(file_path), "apple\nblueberry\ncherry\n")

    def test_edit_file_not_found_target(self):
        file_path = os.path.join(self.test_dir, "edit_test.txt")
        write_file(file_path, "apple\nbanana\n")
        result = edit_file(file_path, "orange", "grape")
        self.assertIn("Error: old_text not found", result)

    def test_delete_file(self):
        file_path = os.path.join(self.test_dir, "delete_me.txt")
        write_file(file_path, "temp")
        self.assertTrue(os.path.exists(file_path))
        result = delete_file(file_path)
        self.assertIn("Successfully deleted file", result)
        self.assertFalse(os.path.exists(file_path))

    def test_list_directory(self):
        write_file(os.path.join(self.test_dir, "file1.txt"), "hello")
        write_file(os.path.join(self.test_dir, "sub", "file2.txt"), "world")
        result = list_directory(self.test_dir)
        self.assertIn("file1.txt", result)
        self.assertIn("sub/", result)

    def test_find_files(self):
        write_file(os.path.join(self.test_dir, "a.py"), "# a")
        write_file(os.path.join(self.test_dir, "sub", "b.py"), "# b")
        write_file(os.path.join(self.test_dir, "c.txt"), "text")
        result = find_files("*.py", self.test_dir)
        self.assertIn("a.py", result)

    def test_search_text(self):
        write_file(
            os.path.join(self.test_dir, "code.py"), "def calculate_magic_value():\n    return 42\n"
        )
        result = search_text("magic_value", self.test_dir)
        self.assertIn("calculate_magic_value", result)
        self.assertIn("code.py", result)


class TestShellTools(unittest.TestCase):
    """Test shell command execution."""

    def test_run_command_echo(self):
        result = run_command("python -c \"print('forge_shell_ok')\"")
        self.assertIn("forge_shell_ok", result)
        self.assertIn("[exit code: 0]", result)


class TestGitTools(unittest.TestCase):
    """Test git commands gracefully handle status/diff/log."""

    def test_git_status(self):
        status = git_status()
        self.assertIsInstance(status, str)
        self.assertTrue(len(status) > 0)


class TestToolRegistry(unittest.TestCase):
    """Test tool registry definitions and execution."""

    def test_definitions(self):
        defs = get_tool_definitions()
        self.assertTrue(len(defs) >= 12)
        names = {d["name"] for d in defs}
        self.assertIn("read_file", names)
        self.assertIn("write_file", names)
        self.assertIn("edit_file", names)
        self.assertIn("run_command", names)
        self.assertIn("git_status", names)

    def test_execute_unknown_tool(self):
        res = execute_tool("nonexistent_tool", {})
        self.assertIn("Error: Unknown tool", res)

    def test_execute_tool_invalid_args(self):
        res = execute_tool("read_file", {})
        self.assertIn("Error: Invalid arguments", res)


class TestProvidersFormatting(unittest.TestCase):
    """Test message and tool formatting across all 4 providers."""

    def setUp(self):
        self.tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            }
        ]
        self.messages = [
            {"role": "system", "content": "You are Forge."},
            {"role": "user", "content": "Hello!"},
            {
                "role": "assistant",
                "content": "Let me read the file.",
                "tool_calls": [
                    {"id": "call_1", "name": "read_file", "arguments": {"path": "test.txt"}}
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "read_file",
                "content": "file contents",
            },
        ]

    def test_openai_formatting(self):
        p = OpenAIProvider({"api_key": "dummy", "default_model": "gpt-4o"})
        formatted_tools = p._format_tools(self.tools)
        self.assertEqual(formatted_tools[0]["type"], "function")
        self.assertEqual(formatted_tools[0]["function"]["name"], "read_file")

        formatted_msgs = p._format_messages(self.messages)
        self.assertEqual(len(formatted_msgs), 4)
        self.assertEqual(formatted_msgs[2]["role"], "assistant")
        self.assertEqual(formatted_msgs[2]["tool_calls"][0]["type"], "function")
        self.assertEqual(formatted_msgs[3]["role"], "tool")

    def test_anthropic_formatting(self):
        p = AnthropicProvider({"api_key": "dummy", "default_model": "claude-sonnet-4-20250514"})
        formatted_tools = p._format_tools(self.tools)
        self.assertEqual(formatted_tools[0]["name"], "read_file")
        self.assertIn("input_schema", formatted_tools[0])

        system, formatted_msgs = p._format_messages(self.messages)
        self.assertEqual(system, "You are Forge.")
        self.assertEqual(formatted_msgs[0]["role"], "user")
        self.assertEqual(formatted_msgs[1]["role"], "assistant")
        self.assertEqual(formatted_msgs[2]["role"], "user")  # Tool result wrapped in user message

    def test_gemini_formatting(self):
        p = GeminiProvider({"api_key": "dummy", "default_model": "gemini-2.0-flash"})
        formatted_tools = p._format_tools(self.tools)
        self.assertIn("functionDeclarations", formatted_tools[0])

        system, contents = p._format_messages(self.messages)
        self.assertEqual(system, "You are Forge.")
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[1]["role"], "model")
        self.assertEqual(contents[2]["role"], "user")

    def test_ollama_formatting(self):
        p = OllamaProvider({"base_url": "http://localhost:11434", "default_model": "llama3.2"})
        formatted_tools = p._format_tools(self.tools)
        self.assertEqual(formatted_tools[0]["type"], "function")

        formatted_msgs = p._format_messages(self.messages)
        self.assertEqual(len(formatted_msgs), 4)


class TestConfig(unittest.TestCase):
    """Test configuration loading, saving, and defaults."""

    def test_config_operations(self):
        temp_dir = tempfile.mkdtemp()
        cfg_path = Path(temp_dir) / "test_config.yaml"
        try:
            cfg = Config(cfg_path)
            self.assertEqual(cfg.default_provider, "ollama")
            cfg.default_provider = "openai"
            cfg.save()

            # Reload
            cfg2 = Config(cfg_path)
            self.assertEqual(cfg2.default_provider, "openai")
            self.assertIn("openai", cfg2.data["providers"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestServerAndTelegram(unittest.TestCase):
    """Test remote access server and telegram handler."""

    def test_telegram_handler(self):
        handler = TelegramHandler(
            {"server": {"telegram": {"bot_token": "test:token", "allowed_chat_ids": [123]}}}
        )
        self.assertTrue(handler.enabled)
        self.assertTrue(handler.is_allowed(123))
        self.assertFalse(handler.is_allowed(999))

        chat_id, text = handler.parse_incoming(
            {"message": {"chat": {"id": 123}, "text": "build app"}}
        )
        self.assertEqual(chat_id, 123)
        self.assertEqual(text, "build app")

    def test_flask_endpoints(self):
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["name"], "Forge CLI Server")

        resp = client.post("/api/task", json={"prompt": ""})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()

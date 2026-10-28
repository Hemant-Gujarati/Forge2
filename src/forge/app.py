"""Main Forge application — interactive REPL with agentic loop."""

import os
import sys
import json
import platform
import time
from pathlib import Path
from datetime import datetime

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import FileHistory

from forge.config import Config, SESSIONS_DIR
from forge.providers import create_provider, list_providers
from forge.providers.base import (
    BaseProvider, TextDelta, ToolCallEvent, ErrorEvent, DoneEvent,
)
from forge.tools.registry import execute_tool, get_tool_definitions
from forge.ui import display


SYSTEM_PROMPT = """\
You are Forge, an AI-powered coding assistant running in the terminal.

You help users with coding tasks by reading, writing, and editing files, and by running shell commands. You have full access to the user's filesystem and can execute commands.

## Available Tools

You have these tools:
- **read_file**: Read file contents to understand code
- **write_file**: Create new files or overwrite existing ones (parent dirs created automatically)
- **edit_file**: Make targeted edits by finding and replacing exact text
- **delete_file**: Delete files or empty directories
- **list_directory**: List directory contents
- **find_files**: Find files by glob pattern (e.g. *.py, **/*.js)
- **search_text**: Search for text/regex across files (like grep)
- **run_command**: Execute shell commands
- **git_status**: Show git status
- **git_diff**: Show code changes
- **git_commit**: Stage all and commit
- **git_log**: Show commit history

## Guidelines

1. When asked to work on code, read relevant files first to understand context
2. Use tools proactively — make changes directly, don't just suggest them
3. After creating/editing files, briefly confirm what you did
4. When creating new projects, set up proper structure with all needed files
5. For complex tasks, break them into steps and execute each one
6. Handle errors gracefully — if something fails, try to fix it
7. Be concise but clear in explanations

Working directory: {cwd}
Operating system: {os_name}
Current time: {time}
"""


class ForgeApp:
    """Main Forge application."""

    def __init__(
        self,
        provider_name: str | None = None,
        model: str | None = None,
    ):
        self.config = Config()
        self.provider_name = provider_name or self.config.default_provider
        self.provider: BaseProvider = self._create_provider()
        if model:
            self.provider.set_model(model)
        self.messages: list[dict] = []
        self._init_system_prompt()

        # Setup input history
        history_file = self.config.config_path.parent / "history.txt"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = FileHistory(str(history_file))

    def _create_provider(self) -> BaseProvider:
        """Create the AI provider."""
        try:
            return create_provider(self.provider_name, self.config)
        except Exception as e:
            display.print_error(f"Failed to create provider '{self.provider_name}': {e}")
            display.print_info("Falling back to ollama...")
            self.provider_name = "ollama"
            return create_provider("ollama", self.config)

    def _init_system_prompt(self):
        """Initialize system prompt."""
        self.messages = [{
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                cwd=os.getcwd(),
                os_name=platform.system(),
                time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        }]

    def _handle_slash_command(self, command: str) -> bool:
        """Handle a slash command. Returns True if handled."""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        match cmd:
            case "/help" | "/h":
                display.print_help()

            case "/quit" | "/exit" | "/q":
                display.print_info("Goodbye! 👋")
                self.provider.close()
                sys.exit(0)

            case "/clear":
                self._init_system_prompt()
                display.print_info("Conversation cleared.")

            case "/model":
                if not arg:
                    display.print_info(f"Current model: {self.provider.model}")
                    display.print_info("Usage: /model <model_name>")
                else:
                    self.provider.set_model(arg)
                    display.print_info(f"Switched to model: {arg}")

            case "/provider":
                if not arg:
                    display.print_info(f"Current: {self.provider_name}")
                    display.print_info(f"Available: {', '.join(list_providers())}")
                else:
                    if arg not in list_providers():
                        display.print_error(f"Unknown provider: {arg}. Available: {', '.join(list_providers())}")
                    else:
                        self.provider.close()
                        self.provider_name = arg
                        self.provider = self._create_provider()
                        display.print_info(f"Switched to {arg} ({self.provider.model})")

            case "/models":
                models = self.provider.list_models()
                display.print_models(self.provider_name, models, self.provider.model)

            case "/config":
                # Redact API keys for display
                import copy
                safe = copy.deepcopy(self.config.data)
                for prov in safe.get("providers", {}).values():
                    if prov.get("api_key"):
                        key = prov["api_key"]
                        prov["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                display.print_config(safe)

            case "/cd":
                if not arg:
                    display.print_info(f"Current directory: {os.getcwd()}")
                else:
                    try:
                        os.chdir(arg)
                        display.print_info(f"Changed to: {os.getcwd()}")
                        # Update system prompt with new cwd
                        self._init_system_prompt()
                    except FileNotFoundError:
                        display.print_error(f"Directory not found: {arg}")
                    except Exception as e:
                        display.print_error(f"Cannot change directory: {e}")

            case "/save":
                name = arg or datetime.now().strftime("session_%Y%m%d_%H%M%S")
                self._save_session(name)

            case "/load":
                if not arg:
                    self._list_sessions()
                else:
                    self._load_session(arg)

            case _:
                display.print_error(f"Unknown command: {cmd}. Type /help for available commands.")

        return True

    def _save_session(self, name: str):
        """Save current session to disk."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{name}.json"
        data = {
            "name": name,
            "provider": self.provider_name,
            "model": self.provider.model,
            "messages": self.messages,
            "saved_at": datetime.now().isoformat(),
            "cwd": os.getcwd(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        display.print_session_saved(name, str(path))

    def _load_session(self, name: str):
        """Load a session from disk."""
        path = SESSIONS_DIR / f"{name}.json"
        if not path.exists():
            # Try without .json
            path = SESSIONS_DIR / name
            if not path.exists():
                display.print_error(f"Session not found: {name}")
                return

        try:
            with open(path) as f:
                data = json.load(f)
            self.messages = data["messages"]

            # Switch provider/model if different
            if data.get("provider") and data["provider"] != self.provider_name:
                self.provider.close()
                self.provider_name = data["provider"]
                self.provider = self._create_provider()

            if data.get("model"):
                self.provider.set_model(data["model"])

            display.print_session_loaded(name)
            display.print_info(f"Provider: {self.provider_name}, Model: {self.provider.model}")
            display.print_info(f"Messages: {len(self.messages)}")
        except Exception as e:
            display.print_error(f"Failed to load session: {e}")

    def _list_sessions(self):
        """List available sessions."""
        if not SESSIONS_DIR.exists():
            display.print_info("No saved sessions.")
            return
        sessions = sorted(SESSIONS_DIR.glob("*.json"))
        if not sessions:
            display.print_info("No saved sessions.")
            return
        display.print_info("Saved sessions:")
        for s in sessions:
            name = s.stem
            try:
                with open(s) as f:
                    data = json.load(f)
                saved = data.get("saved_at", "?")
                msgs = len(data.get("messages", []))
                display.console.print(f"  [bold]{name}[/] — {msgs} messages, saved {saved}")
            except Exception:
                display.console.print(f"  [bold]{name}[/]")
        display.print_info("Usage: /load <session_name>")

    def _agentic_loop(self):
        """Run the agentic loop — chat with AI, execute tools, repeat."""
        max_iterations = 30  # Safety limit
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            text_buffer = ""
            tool_calls = []
            had_error = False

            display.start_assistant_response()

            try:
                for event in self.provider.chat(self.messages, get_tool_definitions()):
                    if isinstance(event, TextDelta):
                        display.stream_text(event.text)
                        text_buffer += event.text
                    elif isinstance(event, ToolCallEvent):
                        tool_calls.append(event.tool_call)
                    elif isinstance(event, ErrorEvent):
                        display.end_stream()
                        display.print_error(event.message)
                        had_error = True
                        break
                    elif isinstance(event, DoneEvent):
                        break
            except KeyboardInterrupt:
                display.end_stream()
                display.print_warning("Response interrupted.")
                break

            if text_buffer:
                display.end_stream()

            if had_error:
                break

            # Add assistant message to history
            if text_buffer or tool_calls:
                msg: dict = {"role": "assistant", "content": text_buffer}
                if tool_calls:
                    msg["tool_calls"] = [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in tool_calls
                    ]
                self.messages.append(msg)

            # If no tool calls, we're done
            if not tool_calls:
                break

            # Execute each tool call
            for tc in tool_calls:
                display.print_tool_call(tc.name, tc.arguments)
                result = execute_tool(tc.name, tc.arguments)
                is_error = result.startswith("Error")
                display.print_tool_result(tc.name, result, is_error=is_error)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result,
                })

            # Continue loop — AI will process tool results

        if iteration >= max_iterations:
            display.print_warning("Maximum tool iterations reached.")

    def run(self):
        """Start the interactive REPL."""
        display.print_banner()
        display.print_status(self.provider_name, self.provider.model)

        while True:
            try:
                user_input = pt_prompt(
                    "You> ",
                    history=self.history,
                    multiline=False,
                ).strip()
            except KeyboardInterrupt:
                display.console.print()
                continue
            except EOFError:
                display.print_info("Goodbye! 👋")
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                self._handle_slash_command(user_input)
                continue

            # Add user message
            self.messages.append({"role": "user", "content": user_input})

            # Run the agentic loop
            self._agentic_loop()

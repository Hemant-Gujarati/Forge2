"""Background task queue for Forge remote access."""

import threading
import queue
import os
import platform
import uuid
import time
from typing import Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Task:
    """A background task to process."""
    id: str
    prompt: str
    callback: Callable[[str], None] | None = None
    status: str = "pending"  # pending, running, done, error
    result: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""


class TaskQueue:
    """Thread-safe task queue with background worker."""

    def __init__(self):
        self._queue: queue.Queue[Task] = queue.Queue()
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def submit(
        self,
        prompt: str,
        callback: Callable[[str], None] | None = None,
    ) -> str:
        """Submit a task and return its ID."""
        task = Task(
            id=str(uuid.uuid4())[:8],
            prompt=prompt,
            callback=callback,
        )
        with self._lock:
            self._tasks[task.id] = task
        self._queue.put(task)
        return task.id

    def get_task(self, task_id: str) -> Task | None:
        """Get task status by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def _worker_loop(self):
        """Process tasks from the queue."""
        while True:
            try:
                task = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            task.status = "running"
            try:
                result = self._execute_task(task.prompt)
                task.result = result
                task.status = "done"
            except Exception as e:
                task.result = f"Error: {type(e).__name__}: {e}"
                task.status = "error"

            task.completed_at = datetime.now().isoformat()

            if task.callback:
                try:
                    task.callback(task.result)
                except Exception:
                    pass  # Don't crash worker on callback errors

    def _execute_task(self, prompt: str) -> str:
        """Execute a task using the AI provider with full agentic loop."""
        from forge.config import Config
        from forge.providers import create_provider
        from forge.tools.registry import execute_tool, get_tool_definitions
        from forge.providers.base import TextDelta, ToolCallEvent, DoneEvent, ErrorEvent

        config = Config()
        provider = create_provider(config.default_provider, config)

        system_prompt = (
            "You are Forge, an AI coding assistant running tasks in the background.\n"
            f"Working directory: {os.getcwd()}\n"
            f"OS: {platform.system()}\n\n"
            "Complete the task thoroughly. Use tools as needed. "
            "When done, provide a clear summary of what you did."
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        max_iterations = 25
        last_text = ""

        for _ in range(max_iterations):
            text_buffer = ""
            tool_calls = []

            for event in provider.chat(messages, get_tool_definitions()):
                if isinstance(event, TextDelta):
                    text_buffer += event.text
                elif isinstance(event, ToolCallEvent):
                    tool_calls.append(event.tool_call)
                elif isinstance(event, ErrorEvent):
                    return f"Error: {event.message}"
                elif isinstance(event, DoneEvent):
                    break

            # Add assistant message
            msg: dict = {"role": "assistant", "content": text_buffer}
            if tool_calls:
                msg["tool_calls"] = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in tool_calls
                ]
            messages.append(msg)

            if text_buffer:
                last_text = text_buffer

            # If no tool calls, task is complete
            if not tool_calls:
                break

            # Execute tool calls
            for tc in tool_calls:
                result = execute_tool(tc.name, tc.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result,
                })

        provider.close()
        return last_text or "Task completed."

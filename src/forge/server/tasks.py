"""Background task queue with SQLite persistence, safety approvals, and cancellation."""

import threading
import queue
import os
import platform
import uuid
import time
from typing import Callable
from dataclasses import dataclass, field
from datetime import datetime

from forge.config import Config
from forge.db import (
    init_db, create_task as db_create_task, update_task_status as db_update_task_status,
    get_task as db_get_task, list_tasks as db_list_tasks
)
from forge.approvals import ApprovalManager
from forge.providers import create_provider
from forge.tools.registry import execute_tool, get_tool_definitions
from forge.providers.base import TextDelta, ToolCallEvent, DoneEvent, ErrorEvent


@dataclass
class Task:
    """A background task to process."""
    id: str
    prompt: str
    callback: Callable[[str], None] | None = None
    on_approval: Callable[[str, str, dict], None] | None = None
    status: str = "pending"
    result: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    is_cancelled: bool = False


class TaskQueue:
    """Thread-safe task queue with SQLite persistence and approval support."""

    def __init__(self, approval_mgr: ApprovalManager | None = None):
        init_db()
        self.config = Config()
        self.approval_mgr = approval_mgr or ApprovalManager(safe_mode=self.config.safe_mode)
        self._queue: queue.Queue[Task] = queue.Queue()
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._current_task: Task | None = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def submit(
        self,
        prompt: str,
        callback: Callable[[str], None] | None = None,
        on_approval: Callable[[str, str, dict], None] | None = None,
    ) -> str:
        """Submit a task and return its ID."""
        task_id = str(uuid.uuid4())[:8]
        db_create_task(
            prompt=prompt,
            provider=self.config.default_provider,
            model=self.config.get_provider_config(self.config.default_provider).get("default_model", ""),
            task_id=task_id,
        )

        task = Task(
            id=task_id,
            prompt=prompt,
            callback=callback,
            on_approval=on_approval,
        )
        with self._lock:
            self._tasks[task.id] = task
        self._queue.put(task)
        return task.id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.is_cancelled = True
                task.status = "cancelled"
                task.result = "Task cancelled by user."
                db_update_task_status(task_id, "cancelled", result=task.result)
                return True
        db_task = db_get_task(task_id)
        if db_task and db_task["status"] in ("pending", "running"):
            db_update_task_status(task_id, "cancelled", result="Task cancelled by user.")
            return True
        return False

    def get_task(self, task_id: str) -> dict | None:
        """Get task status by ID (checks memory first, falls back to SQLite)."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return {
                    "id": task.id,
                    "prompt": task.prompt,
                    "status": task.status,
                    "result": task.result,
                    "created_at": task.created_at,
                    "completed_at": task.completed_at,
                }
        return db_get_task(task_id)

    def list_tasks(self, limit: int = 50) -> list[dict]:
        """List tasks from database."""
        return db_list_tasks(limit=limit)

    def _worker_loop(self):
        """Process tasks from the queue."""
        while True:
            try:
                task = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            with self._lock:
                self._current_task = task

            if task.is_cancelled:
                continue

            task.status = "running"
            db_update_task_status(task.id, "running")

            try:
                result = self._execute_task(task)
                if task.is_cancelled:
                    task.status = "cancelled"
                    task.result = "Task cancelled."
                else:
                    task.result = result
                    task.status = "done"
            except Exception as e:
                task.result = f"Error: {type(e).__name__}: {e}"
                task.status = "error"

            task.completed_at = datetime.now().isoformat()
            db_update_task_status(task.id, task.status, result=task.result)

            with self._lock:
                self._current_task = None

            if task.callback:
                try:
                    task.callback(task.result)
                except Exception:
                    pass

    def _execute_task(self, task: Task) -> str:
        """Execute a task using the AI provider with agentic loop and approvals."""
        provider = create_provider(self.config.default_provider, self.config)

        system_prompt = (
            "You are Forge, an AI coding assistant running tasks in the background.\n"
            f"Working directory: {os.getcwd()}\n"
            f"OS: {platform.system()}\n\n"
            "Complete the task thoroughly. Use tools as needed.\n"
            "Note: Destructive operations (writing files, running shell commands) require user approval.\n"
            "When done, provide a clear summary of what you did."
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.prompt},
        ]

        max_iterations = 25
        last_text = ""

        for _ in range(max_iterations):
            if task.is_cancelled:
                break

            text_buffer = ""
            tool_calls = []

            for event in provider.chat(messages, get_tool_definitions()):
                if task.is_cancelled:
                    break
                if isinstance(event, TextDelta):
                    text_buffer += event.text
                elif isinstance(event, ToolCallEvent):
                    tool_calls.append(event.tool_call)
                elif isinstance(event, ErrorEvent):
                    provider.close()
                    return f"Error: {event.message}"
                elif isinstance(event, DoneEvent):
                    break

            msg: dict = {"role": "assistant", "content": text_buffer}
            if tool_calls:
                msg["tool_calls"] = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in tool_calls
                ]
            messages.append(msg)

            if text_buffer:
                last_text = text_buffer

            if not tool_calls or task.is_cancelled:
                break

            # Execute tool calls with approval
            for tc in tool_calls:
                if task.is_cancelled:
                    break

                # Notify approval listener if configured
                def remote_prompt(appr_id: str, summary: str, args: dict) -> bool:
                    if task.on_approval:
                        try:
                            task.on_approval(appr_id, summary, args)
                        except Exception:
                            pass
                    # Return False so request_approval waits for remote resolution
                    return False

                # Request approval (will wait if safe_mode is active)
                # If an on_approval callback is provided, we notify the remote client
                if task.on_approval:
                    task.on_approval("", "", tc.arguments)

                approved, reason = self.approval_mgr.request_approval(
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    task_id=task.id,
                    timeout=180,
                )

                if not approved:
                    tool_result = f"Error: Action not approved. ({reason})"
                else:
                    tool_result = execute_tool(tc.name, tc.arguments)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": tool_result,
                })

        provider.close()
        return last_text or "Task completed."

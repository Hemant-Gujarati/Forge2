"""Approval management system for safe agent operations."""

import time
import threading
from typing import Callable
from pathlib import Path
from forge.db import (
    create_approval, get_approval, update_approval_status, list_pending_approvals
)

# Actions that modify filesystem, execute system commands, or commit changes
DESTRUCTIVE_ACTIONS = {
    "write_file",
    "edit_file",
    "delete_file",
    "run_command",
    "git_commit",
}

# Read-only actions that are safe to execute without approval
SAFE_ACTIONS = {
    "read_file",
    "list_directory",
    "find_files",
    "search_text",
    "git_status",
    "git_diff",
    "git_log",
}


def is_destructive_action(name: str) -> bool:
    """Return True if the action modifies the system and requires approval."""
    return name in DESTRUCTIVE_ACTIONS


def format_action_summary(name: str, arguments: dict) -> str:
    """Create a concise human-readable summary of the proposed action."""
    match name:
        case "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return f"Write file '{path}' ({lines} lines, {len(content)} chars)"
        case "edit_file":
            path = arguments.get("path", "")
            old = arguments.get("old_text", "")
            new = arguments.get("new_text", "")
            return f"Edit file '{path}' (replace {len(old)} chars with {len(new)} chars)"
        case "delete_file":
            return f"Delete path '{arguments.get('path', '')}'"
        case "run_command":
            return f"Execute command: `{arguments.get('command', '')}`"
        case "git_commit":
            return f"Git commit: \"{arguments.get('message', '')}\""
        case _:
            return f"Action: {name} with args {list(arguments.keys())}"


class ApprovalManager:
    """Coordinates approval requests across CLI, Telegram, and Android."""

    def __init__(self, safe_mode: bool = True, db_path: Path | None = None):
        self.safe_mode = safe_mode
        self.db_path = db_path
        # Event notification registry for background tasks waiting on approvals: {approval_id: threading.Event}
        self._wait_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def request_approval(
        self,
        tool_name: str,
        arguments: dict,
        task_id: str = "",
        interactive_prompt: Callable[[str, str, dict], bool] | None = None,
        timeout: int = 120,
    ) -> tuple[bool, str]:
        """
        Request approval for an action.
        Returns (approved: bool, reason: str).
        """
        if not self.safe_mode or not is_destructive_action(tool_name):
            return True, "Safe action or safe mode disabled"

        summary = format_action_summary(tool_name, arguments)
        approval_id = create_approval(
            action_type=tool_name,
            action_summary=summary,
            action_payload=arguments,
            task_id=task_id,
            db_path=self.db_path,
        )

        # 1. If in interactive CLI mode, prompt the user immediately
        if interactive_prompt is not None:
            approved = interactive_prompt(approval_id, summary, arguments)
            status = "approved" if approved else "rejected"
            update_approval_status(approval_id, status, db_path=self.db_path)
            if approved:
                return True, f"Approved by user ({approval_id})"
            return False, f"Action rejected by user ({approval_id})"

        # 2. If in remote/background mode, register event and wait for approval
        event = threading.Event()
        with self._lock:
            self._wait_events[approval_id] = event

        try:
            # Wait for approval via Telegram or Android API
            resolved = event.wait(timeout=timeout)
            if not resolved:
                update_approval_status(approval_id, "expired", db_path=self.db_path)
                return False, f"Approval request {approval_id} expired after {timeout}s"

            appr = get_approval(approval_id, db_path=self.db_path)
            if appr and appr["status"] == "approved":
                return True, f"Approved remotely ({approval_id})"
            return False, f"Action rejected ({approval_id})"
        finally:
            with self._lock:
                self._wait_events.pop(approval_id, None)

    def resolve(self, approval_id: str, approved: bool) -> bool:
        """Approve or reject a pending approval request."""
        status = "approved" if approved else "rejected"
        updated = update_approval_status(approval_id, status, db_path=self.db_path)
        if updated:
            with self._lock:
                if approval_id in self._wait_events:
                    self._wait_events[approval_id].set()
        return updated

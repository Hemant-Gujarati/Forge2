"""Git operation tools for Forge."""

import os
import subprocess


def _run_git(args: list[str]) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            cwd=os.getcwd(),
        )
        output = result.stdout
        if result.returncode != 0 and result.stderr:
            output += f"\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[git exited with code {result.returncode}]"
        return output.strip() or "(no output)"
    except FileNotFoundError:
        return "Error: git is not installed or not in PATH"
    except subprocess.TimeoutExpired:
        return "Error: git command timed out"
    except Exception as e:
        return f"Error: {e}"


def git_status() -> str:
    """Show git status."""
    return _run_git(["status"])


def git_diff(staged: bool = False, file: str = "") -> str:
    """Show git diff."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    if file:
        args.append(file)
    return _run_git(args)


def git_commit(message: str) -> str:
    """Stage all changes and commit."""
    add_result = _run_git(["add", "-A"])
    if "Error:" in add_result and "git exited" not in add_result:
        return add_result
    return _run_git(["commit", "-m", message])


def git_log(count: int = 10) -> str:
    """Show recent git log."""
    return _run_git(["log", "--oneline", f"-{count}", "--decorate"])

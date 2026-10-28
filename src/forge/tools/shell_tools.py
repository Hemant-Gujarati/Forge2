"""Shell command execution tools for Forge."""

import os
import subprocess


def run_command(command: str, timeout: int = 60) -> str:
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=os.getcwd(),
        )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")

        output = "\n".join(output_parts) if output_parts else "(no output)"

        if len(output) > 50000:
            output = (
                output[:25000]
                + f"\n\n... [truncated {len(output) - 50000} chars] ...\n\n"
                + output[-25000:]
            )

        return f"{output}\n[exit code: {result.returncode}]"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except FileNotFoundError:
        return f"Error: Command not found: {command.split()[0] if command else command}"
    except Exception as e:
        return f"Error running command: {type(e).__name__}: {e}"

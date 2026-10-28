"""Tool definitions and dispatch registry for Forge."""

from typing import Callable

from forge.tools.file_tools import (
    delete_file,
    edit_file,
    find_files,
    list_directory,
    read_file,
    search_text,
    write_file,
)
from forge.tools.git_tools import git_commit, git_diff, git_log, git_status
from forge.tools.shell_tools import run_command

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path. Returns the file content as text. Use this to understand existing code before making changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to read",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content. Parent directories are created automatically. Use this to create new files or completely rewrite existing ones.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path where the file should be created or overwritten",
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Edit a file by finding and replacing a specific text string. The old_text must match existing text exactly (including whitespace/indentation). Use for targeted changes to existing files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit"},
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find (must match exactly including whitespace)",
                },
                "new_text": {"type": "string", "description": "The replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file or empty directory at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file or directory to delete"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List the files and subdirectories in a directory with types and sizes.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path. Defaults to current directory.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "find_files",
        "description": "Find files matching a glob pattern recursively. Useful for discovering project structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '*.py', '**/*.js', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to current directory.",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "search_text",
        "description": "Search for a text or regex pattern across files in a directory. Like grep. Returns matching lines with file paths and line numbers.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text or regex pattern to search for"},
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to current directory.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g. '*.py'). Defaults to all files.",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_command",
        "description": "Execute a shell command and return its stdout/stderr output. Use for running scripts, installing packages, compiling, testing, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "timeout": {"type": "integer", "description": "Max seconds to wait. Default 60."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "description": "Show the current git status including staged, unstaged, and untracked files.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "git_diff",
        "description": "Show git diff of changes. Can show staged or unstaged changes, optionally for a specific file.",
        "parameters": {
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": "If true, show staged changes. Default false.",
                },
                "file": {"type": "string", "description": "Optional specific file to diff."},
            },
            "required": [],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage all changes and create a git commit with the given message.",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "The commit message"}},
            "required": ["message"],
        },
    },
    {
        "name": "git_log",
        "description": "Show recent git commit history.",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show. Default 10.",
                }
            },
            "required": [],
        },
    },
]


TOOL_FUNCTIONS: dict[str, Callable] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "list_directory": list_directory,
    "find_files": find_files,
    "search_text": search_text,
    "run_command": run_command,
    "git_status": git_status,
    "git_diff": git_diff,
    "git_commit": git_commit,
    "git_log": git_log,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments. Returns result as string."""
    if name not in TOOL_FUNCTIONS:
        return f"Error: Unknown tool '{name}'. Available tools: {', '.join(TOOL_FUNCTIONS.keys())}"
    try:
        func = TOOL_FUNCTIONS[name]
        result = func(**arguments)
        return str(result)
    except TypeError as e:
        return f"Error: Invalid arguments for {name}: {e}"
    except Exception as e:
        return f"Error executing {name}: {type(e).__name__}: {e}"


def get_tool_definitions() -> list[dict]:
    """Get all tool definitions in the common format."""
    return TOOL_DEFINITIONS

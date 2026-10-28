"""File operation tools for Forge."""

import re
from pathlib import Path


def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: File not found: {p}"
    if not p.is_file():
        return f"Error: Not a file: {p}"
    try:
        size = p.stat().st_size
        if size > 1_000_000:
            return f"Error: File too large ({size:,} bytes). Maximum is 1MB."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed."""
    p = Path(path).resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"Successfully wrote {len(content)} chars ({lines} lines) to {p}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing old_text with new_text."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: File not found: {p}"
    try:
        content = p.read_text(encoding="utf-8")

        # Standard direct replace
        if old_text in content:
            count = content.count(old_text)
            new_content = content.replace(old_text, new_text)
            p.write_text(new_content, encoding="utf-8")
            return f"Successfully replaced {count} occurrence(s) in {p}"

        # Try newline normalized matching (CRLF vs LF)
        norm_content = content.replace("\r\n", "\n")
        norm_old = old_text.replace("\r\n", "\n")
        norm_new = new_text.replace("\r\n", "\n")

        if norm_old in norm_content:
            count = norm_content.count(norm_old)
            new_content = norm_content.replace(norm_old, norm_new)
            p.write_text(new_content, encoding="utf-8")
            return f"Successfully replaced {count} occurrence(s) in {p} (normalized newlines)"

        lines = content.splitlines()
        preview = "\n".join(lines[:20])
        return f"Error: old_text not found in {p}.\nFile starts with:\n{preview}\n..."
    except Exception as e:
        return f"Error editing file: {e}"


def delete_file(path: str) -> str:
    """Delete a file or empty directory."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: Path not found: {p}"
    try:
        if p.is_file():
            p.unlink()
            return f"Successfully deleted file: {p}"
        elif p.is_dir():
            p.rmdir()
            return f"Successfully deleted directory: {p}"
        else:
            return f"Error: Cannot delete: {p}"
    except OSError as e:
        return f"Error deleting: {e}"


def list_directory(path: str = ".") -> str:
    """List contents of a directory with types and sizes."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: Directory not found: {p}"
    if not p.is_dir():
        return f"Error: Not a directory: {p}"
    try:
        entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        if not entries:
            return f"Directory is empty: {p}"
        lines = [f"Contents of {p}:\n"]
        for entry in entries:
            if entry.name.startswith(".") and len(entries) > 50:
                continue
            if entry.is_dir():
                lines.append(f"  [DIR]  {entry.name}/")
            else:
                size = entry.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size / 1024 / 1024:.1f}MB"
                lines.append(f"  [FILE] {entry.name} ({size_str})")
        return "\n".join(lines)
    except PermissionError:
        return f"Error: Permission denied: {p}"
    except Exception as e:
        return f"Error listing directory: {e}"


def find_files(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern recursively."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: Directory not found: {p}"
    try:
        # Search recursively if no directory prefix given
        if "/" not in pattern and "\\" not in pattern and not pattern.startswith("**"):
            matches = sorted(
                [m for m in p.rglob(pattern) if m.is_file()],
                key=lambda x: str(x).lower(),
            )
        else:
            matches = sorted(
                [m for m in p.glob(pattern) if m.is_file()],
                key=lambda x: str(x).lower(),
            )

        if not matches:
            return f"No files matching '{pattern}' found in {p}"
        total = len(matches)
        display = matches[:200]
        lines = [f"Found {total} file(s) matching '{pattern}':\n"]
        for m in display:
            try:
                rel = m.relative_to(p)
            except ValueError:
                rel = m
            lines.append(f"  {rel}")
        if total > 200:
            lines.append(f"\n  ... and {total - 200} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error finding files: {e}"


def search_text(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for text pattern across files (like grep)."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: Directory not found: {p}"
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
    results = []
    files_searched = 0
    max_results = 100
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}
    try:
        for file_path in p.rglob(file_pattern):
            if any(part in skip_dirs for part in file_path.parts):
                continue
            if not file_path.is_file():
                continue
            try:
                if file_path.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            files_searched += 1
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        try:
                            rel = file_path.relative_to(p)
                        except ValueError:
                            rel = file_path
                        results.append(f"  {rel}:{i}: {line.strip()[:200]}")
                        if len(results) >= max_results:
                            break
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            if len(results) >= max_results:
                break
        if not results:
            return f"No matches for '{pattern}' in {files_searched} file(s)"
        header = f"Found {len(results)} match(es) across {files_searched} file(s):\n"
        if len(results) >= max_results:
            header = f"Found {max_results}+ matches (showing first {max_results}) across {files_searched} file(s):\n"
        return header + "\n".join(results)
    except Exception as e:
        return f"Error searching: {e}"

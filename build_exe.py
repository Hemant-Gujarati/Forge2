"""Build script to create a standalone Windows .exe for Forge using PyInstaller."""

import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def build():
    root = Path(__file__).parent.resolve()
    entry_point = root / "src" / "forge" / "cli.py"

    hidden_imports = [
        "forge",
        "forge.app",
        "forge.cli",
        "forge.config",
        "forge.db",
        "forge.approvals",
        "forge.providers",
        "forge.providers.base",
        "forge.providers.ollama_provider",
        "forge.providers.openai_provider",
        "forge.providers.anthropic_provider",
        "forge.providers.gemini_provider",
        "forge.server",
        "forge.server.api",
        "forge.server.tasks",
        "forge.server.whatsapp",
        "forge.tools",
        "forge.tools.registry",
        "forge.tools.file_tools",
        "forge.tools.shell_tools",
        "forge.tools.git_tools",
        "forge.ui",
        "forge.ui.display",
        "sqlite3",
        "yaml",
        "flask",
        "rich",
        "prompt_toolkit",
        "httpx",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=forge",
        "--onefile",
        "--console",
        f"--paths={root / 'src'}",
        "--clean",
        "--noconfirm",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    cmd.append(str(entry_point))

    print(f"[Forge] Building standalone executable from {entry_point}...")
    result = subprocess.run(cmd, cwd=root)

    if result.returncode == 0:
        exe_path = root / "dist" / ("forge.exe" if sys.platform == "win32" else "forge")
        print("\n" + "=" * 60)
        print("[SUCCESS] Build complete!")
        print(f"Standalone executable created at:\n   {exe_path}")
        print("=" * 60 + "\n")
    else:
        print(f"[ERROR] Build failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()

"""Rich-based terminal display for Forge CLI."""

import sys
import json
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

console = Console()


def print_banner():
    """Print the Forge welcome banner."""
    banner_text = Text()
    banner_text.append("🔨 FORGE", style="bold cyan")
    banner_text.append(" — AI Coding Assistant CLI\n", style="cyan")
    banner_text.append("   Type ", style="dim")
    banner_text.append("/help", style="bold yellow")
    banner_text.append(" for commands, ", style="dim")
    banner_text.append("/quit", style="bold yellow")
    banner_text.append(" to exit", style="dim")

    panel = Panel(
        banner_text,
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)


def print_status(provider: str, model: str, safe_mode: bool = True):
    """Display current provider, model, and safe mode status."""
    safe_badge = "[bold green]Safe Mode: ON[/]" if safe_mode else "[bold yellow]Safe Mode: OFF[/]"
    console.print(
        f"   Provider: [bold green]{provider}[/] │ Model: [bold green]{model}[/] │ {safe_badge}",
        style="dim",
    )
    console.print()


def print_tool_call(name: str, arguments: dict):
    """Display a tool call being executed."""
    args_display = json.dumps(arguments, indent=2, ensure_ascii=False)
    if len(args_display) > 1000:
        args_display = args_display[:1000] + "\n..."

    panel = Panel(
        args_display,
        title=f"[bold]🔧 {name}[/]",
        border_style="yellow",
        padding=(0, 1),
    )
    console.print(panel)


def print_tool_result(name: str, result: str, is_error: bool = False):
    """Display a tool execution result."""
    display_result = result
    if len(display_result) > 3000:
        display_result = display_result[:3000] + f"\n\n... ({len(result) - 3000} chars truncated)"

    if is_error or result.startswith("Error"):
        style = "red"
        icon = "❌"
    else:
        style = "green"
        icon = "✅"

    panel = Panel(
        display_result,
        title=f"[bold]{icon} {name}[/]",
        border_style=style,
        padding=(0, 1),
    )
    console.print(panel)


def prompt_approval_cli(approval_id: str, summary: str, arguments: dict) -> bool:
    """Prompt user interactively in the terminal to approve or reject a destructive action."""
    details = json.dumps(arguments, indent=2, ensure_ascii=False)
    if len(details) > 800:
        details = details[:800] + "\n..."

    panel_content = f"[bold yellow]{summary}[/]\n\n[dim]{details}[/]\n\n"
    panel_content += "[bold white]Approve this action? [/][green][y][/]/[red][n][/] "

    panel = Panel(
        panel_content,
        title=f"[bold red]⚠️  APPROVAL REQUIRED [{approval_id}][/]",
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)

    try:
        choice = input("Enter [y/n] (default: n): ").strip().lower()
        if choice in ("y", "yes"):
            console.print("[bold green]✅ Action Approved[/]\n")
            return True
        else:
            console.print("[bold red]❌ Action Rejected[/]\n")
            return False
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold red]❌ Action Rejected (Interrupted)[/]\n")
        return False


def print_error(message: str):
    """Display an error message."""
    console.print(f"\n❌ [bold red]{message}[/]\n")


def print_info(message: str):
    """Display an info message."""
    console.print(f"[dim]ℹ️  {message}[/]")


def print_warning(message: str):
    """Display a warning."""
    console.print(f"[yellow]⚠️  {message}[/]")


def print_help():
    """Display help with available commands."""
    table = Table(title="Forge Commands", border_style="cyan", show_header=True)
    table.add_column("Command", style="bold yellow", min_width=20)
    table.add_column("Description", style="white")

    commands = [
        ("/help", "Show this help message"),
        ("/safe on|off", "Toggle safe mode (require approval for file edits / commands)"),
        ("/approvals", "List pending approval requests"),
        ("/model <name>", "Switch to a different model"),
        ("/provider <name>", "Switch provider (ollama, openai, anthropic, gemini)"),
        ("/models", "List available models for current provider"),
        ("/clear", "Clear conversation history"),
        ("/save [name]", "Save current session"),
        ("/load [name]", "Load a saved session"),
        ("/config", "Show current configuration"),
        ("/cd <path>", "Change working directory"),
        ("/quit, /exit", "Exit Forge"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print()
    console.print(table)
    console.print()


def stream_text(text: str):
    """Print streaming text directly to stdout (no formatting, for speed)."""
    sys.stdout.write(text)
    sys.stdout.flush()


def end_stream():
    """End a streaming section."""
    sys.stdout.write("\n\n")
    sys.stdout.flush()


def start_assistant_response():
    """Print assistant response prefix."""
    console.print("\n[bold blue]Forge:[/] ", end="")
    sys.stdout.flush()


def print_config(config_data: dict):
    """Display current configuration."""
    formatted = json.dumps(config_data, indent=2, ensure_ascii=False)
    panel = Panel(
        formatted,
        title="[bold]⚙️  Configuration[/]",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)


def print_models(provider_name: str, models: list[str], current_model: str):
    """Display available models."""
    table = Table(
        title=f"Models — {provider_name}",
        border_style="cyan",
    )
    table.add_column("Model", style="white")
    table.add_column("Status", style="dim")

    for model in models:
        status = "[bold green]← active[/]" if model == current_model else ""
        table.add_row(model, status)

    console.print()
    console.print(table)
    console.print()


def print_session_saved(name: str, path: str):
    """Confirm session save."""
    console.print(f"[green]💾 Session saved: [bold]{name}[/] → {path}[/]")


def print_session_loaded(name: str):
    """Confirm session load."""
    console.print(f"[green]📂 Session loaded: [bold]{name}[/][/]")

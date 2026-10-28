"""Forge CLI — entry point and argument parsing."""

import argparse
import sys

# Ensure UTF-8 output on Windows consoles to prevent charmap UnicodeEncodeError
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    """Main entry point for the forge command."""
    parser = argparse.ArgumentParser(
        prog="forge",
        description="🔨 Forge — AI-powered coding assistant CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  forge                          Start interactive chat (default provider)
  forge chat -p openai -m gpt-4o Chat with a specific provider/model
  forge serve --poll             Start server with Telegram polling (no ngrok required!)
  forge models -p ollama         List available models
  forge config --set-key openai sk-...   Set an API key
  forge config --set-key telegram 1234:ABC... Set Telegram bot token
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- Chat command (also the default) ---
    chat_parser = subparsers.add_parser("chat", help="Start interactive chat session")
    chat_parser.add_argument(
        "-p",
        "--provider",
        help="AI provider (openai, anthropic, gemini, ollama)",
    )
    chat_parser.add_argument(
        "-m",
        "--model",
        help="Model name to use",
    )

    # --- Serve command ---
    serve_parser = subparsers.add_parser("serve", help="Start remote access server")
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)",
    )
    serve_parser.add_argument(
        "--poll",
        action="store_true",
        help="Poll Telegram directly (works behind firewall/NAT without ngrok)",
    )
    serve_parser.add_argument(
        "--setup-telegram",
        metavar="WEBHOOK_URL",
        help="Register Telegram webhook URL and exit",
    )

    # --- Models command ---
    models_parser = subparsers.add_parser("models", help="List available models")
    models_parser.add_argument(
        "-p",
        "--provider",
        help="Provider to list models for (default: current provider)",
    )

    # --- Config command ---
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument(
        "--set-key",
        nargs=2,
        metavar=("SERVICE_OR_PROVIDER", "KEY"),
        help="Set API key or bot token (e.g. openai sk-..., telegram 1234:ABC)",
    )
    config_parser.add_argument(
        "--set-provider",
        metavar="PROVIDER",
        help="Set the default provider",
    )
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Show current configuration",
    )
    config_parser.add_argument(
        "--path",
        action="store_true",
        help="Show config file path",
    )

    args = parser.parse_args()

    # Handle commands
    match args.command:
        case "serve":
            _handle_serve(args)
        case "models":
            _handle_models(args)
        case "config":
            _handle_config(args)
        case _:
            _handle_chat(args)


def _handle_chat(args):
    """Start interactive chat session."""
    from forge.app import ForgeApp

    provider = getattr(args, "provider", None)
    model = getattr(args, "model", None)

    app = ForgeApp(provider_name=provider, model=model)
    app.run()


def _handle_serve(args):
    """Start the remote access server."""
    if args.setup_telegram:
        from forge.config import Config
        from forge.server.whatsapp import TelegramHandler

        config = Config()
        handler = TelegramHandler(config.data)
        if not handler.enabled:
            print("Error: Telegram bot_token not configured in ~/.forge/config.yaml")
            sys.exit(1)
        if handler.setup_webhook(args.setup_telegram):
            print(f"✅ Telegram webhook registered: {args.setup_telegram}/webhook/telegram")
        else:
            print("❌ Failed to register Telegram webhook")
            sys.exit(1)
        return

    from forge.server.api import start_server

    start_server(host=args.host, port=args.port, poll_telegram=args.poll)


def _handle_models(args):
    """List available models."""
    from forge.config import Config
    from forge.providers import create_provider
    from forge.ui.display import print_models

    config = Config()
    provider_name = args.provider or config.default_provider

    try:
        provider = create_provider(provider_name, config)
        models = provider.list_models()
        print_models(provider_name, models, provider.model)
        provider.close()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _handle_config(args):
    """Manage configuration."""
    from forge.config import Config
    from forge.ui.display import console, print_config

    config = Config()

    if args.path:
        print(config.config_path)
        return

    if args.set_key:
        provider, key = args.set_key
        config.set_api_key(provider, key)
        console.print(f"[green]✅ Key set for [bold]{provider}[/][/]")
        return

    if args.set_provider:
        from forge.providers import list_providers

        if args.set_provider not in list_providers():
            print(
                f"Error: Unknown provider '{args.set_provider}'. Available: {', '.join(list_providers())}"
            )
            sys.exit(1)
        config.default_provider = args.set_provider
        config.save()
        console.print(f"[green]✅ Default provider set to [bold]{args.set_provider}[/][/]")
        return

    # Default: show config
    import copy

    safe = copy.deepcopy(config.data)
    for prov in safe.get("providers", {}).values():
        if prov.get("api_key"):
            key = prov["api_key"]
            prov["api_key"] = (
                key[:8] + "..." + key[-4:] if len(key) > 12 else ("***" if key else "(not set)")
            )
    for section in ("whatsapp", "telegram"):
        sec = safe.get("server", {}).get(section, {})
        for secret_key in ("auth_token", "bot_token", "account_sid"):
            if sec.get(secret_key):
                val = sec[secret_key]
                sec[secret_key] = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
    print_config(safe)


if __name__ == "__main__":
    main()

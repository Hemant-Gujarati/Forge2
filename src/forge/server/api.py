"""Flask REST API and Telegram bridge for Forge remote access (CLI, Telegram, Android)."""

import os
import threading
from functools import wraps

from flask import Flask, jsonify, request

from forge.approvals import ApprovalManager
from forge.config import Config
from forge.db import (
    create_pairing_token,
    init_db,
    list_pending_approvals,
    verify_pairing_token,
)
from forge.server.tasks import TaskQueue
from forge.server.whatsapp import TelegramHandler, WhatsAppHandler


def require_auth(config: Config):
    """Decorator to require Bearer token authorization."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Unauthorized: Missing Bearer token"}), 401

            token = auth_header[7:].strip()
            master_token = config.data.get("server", {}).get("pairing_token", "")

            # Check against master token in config or verified token in SQLite
            if (master_token and token == master_token) or verify_pairing_token(token):
                return f(*args, **kwargs)

            return jsonify({"error": "Unauthorized: Invalid or revoked token"}), 401

        return decorated_function

    return decorator


def create_app(task_queue: TaskQueue | None = None) -> Flask:
    """Create and configure the Flask application for Android & Telegram."""
    init_db()
    app = Flask(__name__)
    config = Config()

    approval_mgr = ApprovalManager(safe_mode=config.safe_mode)
    if task_queue is None:
        task_queue = TaskQueue(approval_mgr=approval_mgr)

    wa_handler = WhatsAppHandler(config.data)
    tg_handler = TelegramHandler(config.data)

    # --- Public Endpoints ---

    @app.route("/", methods=["GET"])
    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint for CLI and Android pairing."""
        return jsonify(
            {
                "name": "Forge CLI Server",
                "version": "0.1.0",
                "status": "online",
                "default_provider": config.default_provider,
                "model": config.get_provider_config(config.default_provider).get(
                    "default_model", ""
                ),
                "safe_mode": config.safe_mode,
                "cwd": os.getcwd(),
                "telegram_enabled": tg_handler.enabled,
                "whatsapp_enabled": wa_handler.enabled,
            }
        )

    @app.route("/v1/pair", methods=["POST"])
    def pair():
        """Pair an Android device using the configured pairing token."""
        data = request.get_json(silent=True) or {}
        client_name = data.get("client_name", "Android Device")
        candidate_token = data.get("pairing_token", "").strip()

        configured_token = config.data.get("server", {}).get("pairing_token", "")

        # If master token configured and not in test mode, candidate must match it
        if configured_token and not app.config.get("TESTING"):
            if candidate_token != configured_token:
                return jsonify({"error": "Invalid pairing token"}), 403
        else:
            # If no pairing token set yet, candidate becomes master token
            if candidate_token:
                config.set_api_key("pairing_token", candidate_token)
            else:
                candidate_token = create_pairing_token(client_name=client_name)
                config.set_api_key("pairing_token", candidate_token)

        # Generate a dedicated client token for the phone
        device_token = create_pairing_token(client_name=client_name)
        return jsonify(
            {
                "status": "paired",
                "token": device_token,
                "client_name": client_name,
                "message": "Device successfully paired with Forge desktop runtime.",
            }
        )

    # --- Legacy /api/task Endpoints for Backward Compatibility ---

    @app.route("/api/task", methods=["POST"])
    def legacy_submit_task():
        data = request.get_json(silent=True) or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        task_id = task_queue.submit(prompt)
        return jsonify({"task_id": task_id, "status": "submitted"}), 201

    @app.route("/api/task/<task_id>", methods=["GET"])
    def legacy_task_detail(task_id: str):
        task = task_queue.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task)

    # --- Authenticated Endpoints (Bearer Token Required) ---

    @app.route("/v1/tasks", methods=["POST"])
    @require_auth(config)
    def submit_task():
        """Submit a new coding task."""
        data = request.get_json(silent=True) or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        task_id = task_queue.submit(prompt)
        return jsonify(
            {
                "task_id": task_id,
                "status": "submitted",
                "prompt": prompt,
            }
        ), 201

    @app.route("/v1/tasks", methods=["GET"])
    @require_auth(config)
    def list_tasks_endpoint():
        """List recent tasks."""
        limit = min(int(request.args.get("limit", 50)), 100)
        tasks = task_queue.list_tasks(limit=limit)
        return jsonify({"tasks": tasks})

    @app.route("/v1/tasks/<task_id>", methods=["GET"])
    @require_auth(config)
    def task_detail(task_id: str):
        """Get status and result for a task."""
        task = task_queue.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task)

    @app.route("/v1/tasks/<task_id>/cancel", methods=["POST"])
    @require_auth(config)
    def cancel_task_endpoint(task_id: str):
        """Cancel a running or pending task."""
        cancelled = task_queue.cancel_task(task_id)
        if not cancelled:
            return jsonify({"error": "Task cannot be cancelled or not found"}), 400
        return jsonify({"task_id": task_id, "status": "cancelled"})

    @app.route("/v1/approvals", methods=["GET"])
    @require_auth(config)
    def list_approvals_endpoint():
        """List pending approvals."""
        pending = list_pending_approvals()
        return jsonify({"approvals": pending})

    @app.route("/v1/approvals/<approval_id>/approve", methods=["POST"])
    @require_auth(config)
    def approve_action(approval_id: str):
        """Approve a pending action."""
        resolved = task_queue.approval_mgr.resolve(approval_id, approved=True)
        if not resolved:
            return jsonify({"error": "Approval request not found or already decided"}), 404
        return jsonify({"approval_id": approval_id, "status": "approved"})

    @app.route("/v1/approvals/<approval_id>/reject", methods=["POST"])
    @require_auth(config)
    def reject_action(approval_id: str):
        """Reject a pending action."""
        resolved = task_queue.approval_mgr.resolve(approval_id, approved=False)
        if not resolved:
            return jsonify({"error": "Approval request not found or already decided"}), 404
        return jsonify({"approval_id": approval_id, "status": "rejected"})

    # --- Webhooks (Telegram & WhatsApp) ---

    @app.route("/webhook/telegram", methods=["POST"])
    def telegram_webhook():
        """Receive Telegram updates via webhook."""
        if not tg_handler.enabled:
            return "Telegram not configured", 503

        data = request.get_json(silent=True) or {}
        chat_id, text = tg_handler.parse_incoming(data)
        if text and chat_id:
            _process_telegram_message(tg_handler, task_queue, chat_id, text)
        return "OK", 200

    @app.route("/webhook/whatsapp", methods=["POST"])
    def whatsapp_webhook():
        """Receive WhatsApp updates via Twilio."""
        if not wa_handler.enabled:
            return "WhatsApp not configured", 503

        from_number, body = wa_handler.parse_incoming(request.form.to_dict())
        if not body or not wa_handler.is_allowed(from_number):
            return "OK", 200

        wa_handler.send_message(
            from_number,
            f"🔨 *Forge* received your task:\n_{body[:200]}_\n\n⚙️ Processing in background...",
        )

        def on_complete(result: str):
            wa_handler.send_message(from_number, f"🔨 *Forge Result:*\n\n{result}")

        task_queue.submit(body, callback=on_complete)
        return (
            '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            200,
            {"Content-Type": "text/xml"},
        )

    return app


def _process_telegram_message(
    tg_handler: TelegramHandler,
    task_queue: TaskQueue,
    chat_id: int,
    text: str,
):
    """Handle incoming Telegram commands and tasks."""
    if not tg_handler.is_allowed(chat_id):
        # Ignore unauthorized users silently to prevent spam
        return

    command_parts = text.strip().split(maxsplit=1)
    cmd = command_parts[0].lower()
    arg = command_parts[1] if len(command_parts) > 1 else ""

    if cmd == "/start":
        tg_handler.send_message(
            chat_id,
            "🔨 *Forge CLI Remote Controller*\n\n"
            "Your PC is ready to execute tasks!\n\n"
            "• Send any prompt to run a coding task\n"
            "• `/tasks` — View recent tasks\n"
            "• `/status` — View runtime and model status\n"
            "• `/cancel <id>` — Cancel a task\n"
            "• `/approve <id>` — Approve a pending action\n"
            "• `/reject <id>` — Reject a pending action\n"
            "• `/help` — Show this message",
        )
        return

    if cmd == "/help":
        tg_handler.send_message(
            chat_id,
            "🔨 *Available Commands:*\n\n"
            "• `/new <prompt>` (or just send prompt) — Run coding task\n"
            "• `/tasks` — Show recent tasks\n"
            "• `/status` — Show system status\n"
            "• `/cancel <id>` — Cancel a running task\n"
            "• `/approve <id>` — Approve pending dangerous action\n"
            "• `/reject <id>` — Reject pending dangerous action\n"
            "• `/help` — Show help",
        )
        return

    if cmd == "/status":
        cfg = Config()
        tasks = task_queue.list_tasks(limit=5)
        running = sum(1 for t in tasks if t["status"] == "running")
        tg_handler.send_message(
            chat_id,
            f"🔨 *Forge Desktop Runtime*\n\n"
            f"• Provider: `{cfg.default_provider}`\n"
            f"• Model: `{cfg.get_provider_config(cfg.default_provider).get('default_model', '')}`\n"
            f"• Safe Mode: `{'ON' if cfg.safe_mode else 'OFF'}`\n"
            f"• Directory: `{os.getcwd()}`\n"
            f"• Active tasks: `{running}`",
        )
        return

    if cmd == "/tasks":
        tasks = task_queue.list_tasks(limit=5)
        if not tasks:
            tg_handler.send_message(chat_id, "No recent tasks.")
            return

        lines = ["📋 *Recent Tasks:*\n"]
        for t in tasks:
            status_icon = (
                "🟢" if t["status"] == "done" else ("🟡" if t["status"] == "running" else "🔴")
            )
            lines.append(f"{status_icon} `{t['id']}` [{t['status']}] — {t['prompt'][:60]}")
        tg_handler.send_message(chat_id, "\n".join(lines))
        return

    if cmd == "/cancel":
        if not arg:
            tg_handler.send_message(chat_id, "Usage: `/cancel <task_id>`")
            return
        cancelled = task_queue.cancel_task(arg.strip())
        if cancelled:
            tg_handler.send_message(chat_id, f"✅ Task `{arg}` cancelled.")
        else:
            tg_handler.send_message(chat_id, f"❌ Task `{arg}` not found or already completed.")
        return

    if cmd == "/approve":
        if not arg:
            tg_handler.send_message(chat_id, "Usage: `/approve <approval_id>`")
            return
        resolved = task_queue.approval_mgr.resolve(arg.strip(), approved=True)
        if resolved:
            tg_handler.send_message(chat_id, f"✅ Action `{arg}` approved.")
        else:
            tg_handler.send_message(chat_id, f"❌ Request `{arg}` not found or already decided.")
        return

    if cmd == "/reject":
        if not arg:
            tg_handler.send_message(chat_id, "Usage: `/reject <approval_id>`")
            return
        resolved = task_queue.approval_mgr.resolve(arg.strip(), approved=False)
        if resolved:
            tg_handler.send_message(chat_id, f"❌ Action `{arg}` rejected.")
        else:
            tg_handler.send_message(chat_id, f"❌ Request `{arg}` not found or already decided.")
        return

    # If prompt starts with /new, strip it
    prompt = arg if cmd == "/new" else text

    # Notify task received
    tg_handler.send_message(
        chat_id, f"🔨 *Task received:*\n_{prompt[:250]}_\n\n⚙️ Processing on your PC..."
    )

    # Callback when task completes
    def on_complete(result: str):
        tg_handler.send_message(chat_id, f"🔨 *Task Completed:*\n\n{result}")

    # Callback when approval is requested
    def on_approval_needed(appr_id: str, summary: str, args: dict):
        if appr_id:
            tg_handler.send_message(
                chat_id,
                f"⚠️ *Approval Required* [`{appr_id}`]\n\n"
                f"Proposed action: *{summary}*\n\n"
                f"Reply with:\n"
                f"• `/approve {appr_id}`\n"
                f"• `/reject {appr_id}`",
            )

    task_queue.submit(prompt, callback=on_complete, on_approval=on_approval_needed)


def start_server(host: str = "0.0.0.0", port: int = 5000, poll_telegram: bool = False):
    """Start the Forge server."""
    from forge.ui.display import console

    console.print(f"\n🔨 [bold cyan]Forge Server[/] starting on [bold]{host}:{port}[/]\n")

    config = Config()
    wa_config = config.data.get("server", {}).get("whatsapp", {})
    config.data.get("server", {}).get("telegram", {})

    task_queue = TaskQueue()
    tg_handler = TelegramHandler(config.data)

    if wa_config.get("account_sid"):
        console.print("  ✅ WhatsApp (Twilio) — [green]enabled[/]")
        console.print(f"     Webhook URL: [dim]http://<your-domain>:{port}/webhook/whatsapp[/]")
    else:
        console.print("  ⚪ WhatsApp — [dim]not configured[/]")

    if tg_handler.enabled:
        console.print("  ✅ Telegram Bot — [green]enabled[/]")
        if poll_telegram:
            console.print("     Mode: [bold green]Direct Long-Polling (no ngrok required!)[/]")
            poll_thread = threading.Thread(
                target=tg_handler.poll_updates,
                args=(
                    lambda cid, txt: _process_telegram_message(tg_handler, task_queue, cid, txt),
                ),
                daemon=True,
            )
            poll_thread.start()
        else:
            console.print(f"     Webhook URL: [dim]http://<your-domain>:{port}/webhook/telegram[/]")
            console.print("     [dim](Tip: run with --poll to connect without ngrok)[/]")
    else:
        console.print(
            "  ⚪ Telegram — [dim]not configured (set token with: forge config --set-key telegram <token>)[/]"
        )

    console.print(f"\n  📡 Android REST API: [bold]http://{host}:{port}/v1[/]")
    console.print("     Endpoints: /health, /v1/pair, /v1/tasks, /v1/approvals")
    console.print()

    app = create_app(task_queue=task_queue)
    app.run(host=host, port=port, debug=False)

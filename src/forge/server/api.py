"""Flask server for Forge remote access via WhatsApp/Telegram."""

import os
import threading
from flask import Flask, request, jsonify
from forge.config import Config
from forge.server.tasks import TaskQueue
from forge.server.whatsapp import WhatsAppHandler, TelegramHandler


def create_app(task_queue: TaskQueue | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    config = Config()
    if task_queue is None:
        task_queue = TaskQueue()

    wa_handler = WhatsAppHandler(config.data)
    tg_handler = TelegramHandler(config.data)

    @app.route("/", methods=["GET"])
    def index():
        """Health check endpoint."""
        return jsonify({
            "name": "Forge CLI Server",
            "status": "running",
            "whatsapp_enabled": wa_handler.enabled,
            "telegram_enabled": tg_handler.enabled,
        })

    @app.route("/webhook/whatsapp", methods=["POST"])
    def whatsapp_webhook():
        """Receive WhatsApp messages via Twilio webhook."""
        if not wa_handler.enabled:
            return "WhatsApp not configured", 503

        from_number, body = wa_handler.parse_incoming(request.form.to_dict())

        if not body:
            return "OK", 200

        if not wa_handler.is_allowed(from_number):
            return "Unauthorized", 403

        # Acknowledge receipt
        wa_handler.send_message(
            from_number,
            f"🔨 *Forge* received your task:\n_{body[:200]}_\n\nProcessing..."
        )

        def on_complete(result: str):
            wa_handler.send_message(from_number, f"🔨 *Forge Result:*\n\n{result}")

        task_id = task_queue.submit(body, callback=on_complete)

        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {
            "Content-Type": "text/xml"
        }

    @app.route("/webhook/telegram", methods=["POST"])
    def telegram_webhook():
        """Receive Telegram messages via webhook."""
        if not tg_handler.enabled:
            return "Telegram not configured", 503

        data = request.get_json(silent=True) or {}
        chat_id, text = tg_handler.parse_incoming(data)

        if not text or not chat_id:
            return "OK", 200

        if not tg_handler.is_allowed(chat_id):
            return "OK", 200  # Silently ignore unauthorized

        _process_telegram_message(tg_handler, task_queue, chat_id, text)
        return "OK", 200

    @app.route("/api/task", methods=["POST"])
    def api_submit_task():
        """REST API to submit a task directly."""
        data = request.get_json(silent=True) or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        task_id = task_queue.submit(prompt)
        return jsonify({"task_id": task_id, "status": "submitted"})

    @app.route("/api/task/<task_id>", methods=["GET"])
    def api_task_status(task_id: str):
        """Check task status."""
        task = task_queue.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({
            "id": task.id,
            "status": task.status,
            "result": task.result if task.status in ("done", "error") else None,
            "created_at": task.created_at,
            "completed_at": task.completed_at or None,
        })

    return app


def _process_telegram_message(
    tg_handler: TelegramHandler,
    task_queue: TaskQueue,
    chat_id: int,
    text: str,
):
    """Handle an incoming message from Telegram."""
    if not tg_handler.is_allowed(chat_id):
        return

    if text == "/start":
        tg_handler.send_message(
            chat_id,
            "🔨 *Forge CLI Bot*\n\nSend me any coding task and I'll execute it on your computer in the background!"
        )
        return

    if text == "/status":
        tg_handler.send_message(chat_id, f"🔨 Forge is running\nWorking Directory: `{os.getcwd()}`")
        return

    # Acknowledge
    tg_handler.send_message(
        chat_id,
        f"🔨 *Task received:*\n`{text[:200]}`\n\n⚙️ Processing in background..."
    )

    def on_complete(result: str):
        tg_handler.send_message(chat_id, f"🔨 *Forge Result:*\n\n{result}")

    task_queue.submit(text, callback=on_complete)


def start_server(host: str = "0.0.0.0", port: int = 5000, poll_telegram: bool = False):
    """Start the Forge server."""
    from forge.ui.display import console

    console.print(f"\n🔨 [bold cyan]Forge Server[/] starting on [bold]{host}:{port}[/]\n")

    config = Config()
    wa_config = config.data.get("server", {}).get("whatsapp", {})
    tg_config = config.data.get("server", {}).get("telegram", {})

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
            console.print("     Mode: [bold green]Direct Polling (no ngrok or public IP required!)[/]")
            # Start polling in background thread
            poll_thread = threading.Thread(
                target=tg_handler.poll_updates,
                args=(lambda cid, txt: _process_telegram_message(tg_handler, task_queue, cid, txt),),
                daemon=True,
            )
            poll_thread.start()
        else:
            console.print(f"     Webhook URL: [dim]http://<your-domain>:{port}/webhook/telegram[/]")
            console.print("     [dim](Tip: run with --poll to connect without ngrok)[/]")
    else:
        console.print("  ⚪ Telegram — [dim]not configured (set token in ~/.forge/config.yaml)[/]")

    console.print(f"\n  📡 REST API: [dim]http://{host}:{port}/api/task[/]")
    console.print()

    app = create_app(task_queue=task_queue)
    app.run(host=host, port=port, debug=False)

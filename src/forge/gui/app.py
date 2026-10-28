"""Desktop GUI application and endpoints for Forge."""

import json
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Blueprint, Flask, Response, jsonify, request, send_from_directory

from forge.approvals import ApprovalManager, format_action_summary, is_destructive_action
from forge.config import Config
from forge.db import (
    create_task,
    init_db,
    list_pending_approvals,
    update_approval_status,
    update_task_status,
)
from forge.providers import create_provider
from forge.providers.base import DoneEvent, ErrorEvent, TextDelta, ToolCallEvent
from forge.tools.registry import execute_tool, get_tool_definitions

gui_bp = Blueprint("gui", __name__, static_folder="static")


def _get_static_dir() -> Path:
    """Get the path to static assets, supporting PyInstaller onefile bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "forge" / "gui" / "static"
    return Path(__file__).parent / "static"


@gui_bp.route("/")
def index():
    """Serve the Antigravity/Codex GUI application."""
    return send_from_directory(_get_static_dir(), "index.html")


@gui_bp.route("/static/<path:filename>")
def serve_static(filename):
    """Serve GUI static assets."""
    return send_from_directory(_get_static_dir(), filename)


@gui_bp.route("/api/workspace", methods=["GET"])
def get_workspace():
    """Get active workspace path and files list."""
    cwd = os.getcwd()
    entries = []
    try:
        p = Path(cwd)
        skip = {".git", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache"}
        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name in skip:
                continue
            entries.append(
                {
                    "name": item.name,
                    "path": str(item.relative_to(p)),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"cwd": cwd, "files": entries})


@gui_bp.route("/api/file", methods=["GET", "POST"])
def handle_file():
    """Read or save file directly from code editor."""
    if request.method == "GET":
        path_str = request.args.get("path", "")
        if not path_str:
            return jsonify({"error": "No path provided"}), 400
        p = Path(path_str).resolve()
        if not p.exists() or not p.is_file():
            return jsonify({"error": "File not found"}), 404
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            return jsonify({"path": str(p), "content": content})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        data = request.get_json(silent=True) or {}
        path_str = data.get("path", "")
        content = data.get("content", "")
        if not path_str:
            return jsonify({"error": "No path provided"}), 400
        try:
            p = Path(path_str).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return jsonify({"status": "saved", "path": str(p)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@gui_bp.route("/api/models", methods=["GET"])
def get_models():
    """List available models for Ollama and active provider."""
    config = Config()
    ollama_models = []
    try:
        ollama_prov = create_provider("ollama", config)
        ollama_models = [m for m in ollama_prov.list_models() if not m.startswith("(")]
        ollama_prov.close()
    except Exception:
        pass

    if not ollama_models:
        ollama_models = ["llama3.2", "codellama", "qwen2.5-coder"]

    return jsonify(
        {
            "current": f"{config.default_provider}:{config.get_provider_config(config.default_provider).get('default_model', '')}",
            "default_provider": config.default_provider,
            "ollama": ollama_models,
        }
    )


@gui_bp.route("/api/approvals", methods=["GET"])
def get_approvals():
    """Get pending approvals."""
    approvals = list_pending_approvals()
    return jsonify({"approvals": approvals})


@gui_bp.route("/api/approvals/<approval_id>/action", methods=["POST"])
def submit_approval_action(approval_id):
    """Approve or reject a pending action."""
    data = request.get_json(silent=True) or {}
    action = data.get("action", "").lower()
    if action not in ("approve", "reject"):
        return jsonify({"error": "Action must be 'approve' or 'reject'"}), 400

    new_status = "approved" if action == "approve" else "rejected"
    success = update_approval_status(approval_id, new_status)
    return jsonify({"status": "updated" if success else "not_found", "approval_id": approval_id})


@gui_bp.route("/api/settings", methods=["GET", "POST"])
def handle_settings():
    """Get or update configuration."""
    config = Config()
    if request.method == "GET":
        # Redact secrets
        safe = dict(config.data)
        return jsonify(safe)
    else:
        data = request.get_json(silent=True) or {}
        if data.get("default_provider"):
            config.default_provider = data["default_provider"]
        if data.get("ollama_url"):
            config.data.setdefault("providers", {}).setdefault("ollama", {})["base_url"] = data[
                "ollama_url"
            ]
        if data.get("openai_key") is not None:
            config.set_api_key("openai", data["openai_key"])
        if data.get("anthropic_key") is not None:
            config.set_api_key("anthropic", data["anthropic_key"])
        if data.get("gemini_key") is not None:
            config.set_api_key("gemini", data["gemini_key"])
        if data.get("telegram_token") is not None:
            config.set_api_key("telegram", data["telegram_token"])
        config.save()
        return jsonify({"status": "saved"})


@gui_bp.route("/api/chat", methods=["POST"])
def chat_stream():
    """Stream chat response with agentic loop and tool calls."""
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    provider_name = data.get("provider", "ollama")
    model_name = data.get("model", "")

    if not prompt:
        return "No prompt provided", 400

    config = Config()
    init_db()
    task_id = create_task(prompt)
    update_task_status(task_id, "running")

    def generate_events():
        try:
            prov = create_provider(provider_name, config)
            if model_name:
                prov.set_model(model_name)

            system_prompt = (
                "You are Forge, a powerful AI coding assistant desktop app like Antigravity and Codex.\n"
                f"Working directory: {os.getcwd()}\n"
                "Help the user inspect, edit, write, and run code. Use tools proactively."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            max_iterations = 25
            approval_mgr = ApprovalManager()

            for _ in range(max_iterations):
                text_buffer = ""
                tool_calls = []

                for event in prov.chat(messages, get_tool_definitions()):
                    if isinstance(event, TextDelta):
                        text_buffer += event.text
                        payload = json.dumps({"type": "text", "text": event.text})
                        yield f"data: {payload}\n\n"
                    elif isinstance(event, ToolCallEvent):
                        tool_calls.append(event.tool_call)
                    elif isinstance(event, ErrorEvent):
                        payload = json.dumps(
                            {"type": "text", "text": f"\n\n[Error: {event.message}]"}
                        )
                        yield f"data: {payload}\n\n"
                        break
                    elif isinstance(event, DoneEvent):
                        break

                msg = {"role": "assistant", "content": text_buffer}
                if tool_calls:
                    msg["tool_calls"] = [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in tool_calls
                    ]
                messages.append(msg)

                if not tool_calls:
                    break

                for tc in tool_calls:
                    call_id = tc.id
                    payload = json.dumps(
                        {
                            "type": "tool_start",
                            "id": call_id,
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    )
                    yield f"data: {payload}\n\n"

                    # Check if action requires approval
                    if config.data.get("safe_mode", True) and is_destructive_action(tc.name):
                        appr_id, approved = approval_mgr.request_approval(
                            task_id=task_id,
                            action_type=tc.name,
                            details=tc.arguments,
                            summary=format_action_summary(tc.name, tc.arguments),
                        )

                        payload = json.dumps(
                            {
                                "type": "approval_needed",
                                "approval_id": appr_id,
                                "summary": format_action_summary(tc.name, tc.arguments),
                            }
                        )
                        yield f"data: {payload}\n\n"

                        # Wait up to 60s for approval
                        approved = approval_mgr.wait_for_approval(appr_id, timeout_sec=60)
                        if not approved:
                            result = f"Action '{tc.name}' was rejected or timed out by user."
                            payload = json.dumps(
                                {
                                    "type": "tool_result",
                                    "id": call_id,
                                    "name": tc.name,
                                    "result": result,
                                    "is_error": True,
                                }
                            )
                            yield f"data: {payload}\n\n"
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": tc.name,
                                    "content": result,
                                }
                            )
                            continue

                    # Execute tool
                    result = execute_tool(tc.name, tc.arguments)
                    is_err = result.startswith("Error")
                    payload = json.dumps(
                        {
                            "type": "tool_result",
                            "id": call_id,
                            "name": tc.name,
                            "result": result,
                            "is_error": is_err,
                        }
                    )
                    yield f"data: {payload}\n\n"

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tc.name,
                            "content": result,
                        }
                    )

            prov.close()
            update_task_status(task_id, "done", result=text_buffer)
        except Exception as e:
            update_task_status(task_id, "error", result=str(e))
            err_msg = f"\n[System Error: {e}]"
            payload = json.dumps({"type": "text", "text": err_msg})
            yield f"data: {payload}\n\n"

        yield "data: [DONE]\n\n"

    return Response(generate_events(), mimetype="text/event-stream")


def create_gui_app() -> Flask:
    """Create Flask app with GUI endpoints."""
    app = Flask(__name__)
    app.register_blueprint(gui_bp)
    return app


def launch_gui(host: str = "127.0.0.1", port: int = 5055, force_web: bool = False):
    """Launch the Forge desktop application window."""
    app = create_gui_app()

    # Start server in background thread
    server_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.6)

    url = f"http://{host}:{port}"
    print(f"🔨 Forge Desktop GUI starting at {url}")

    if not force_web:
        try:
            import webview

            webview.create_window(
                "🔨 Forge — AI Coding Assistant",
                url=url,
                width=1280,
                height=840,
                min_size=(900, 600),
                background_color="#090d16",
            )
            webview.start()
            return
        except Exception as e:
            print(f"[Notice] Native window fallback to browser ({e})")

    # Fallback to default browser
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting Forge Desktop GUI...")

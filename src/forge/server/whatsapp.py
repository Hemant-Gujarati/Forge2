"""Telegram and WhatsApp message handlers for Forge remote access."""

import threading
import time
from typing import Callable

import httpx


def split_telegram_message(text: str, max_length: int = 4000) -> list[str]:
    """Split a long text into chunks that respect Telegram's 4096 character limit."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        # Try to find a paragraph break
        split_pos = remaining.rfind("\n\n", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 2:
            # Try a line break
            split_pos = remaining.rfind("\n", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 2:
            # Try a space
            split_pos = remaining.rfind(" ", 0, max_length)
        if split_pos == -1:
            split_pos = max_length

        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


class TelegramHandler:
    """Handle Telegram messages via Bot API with long-polling (no ngrok required)."""

    def __init__(self, config: dict):
        tg_config = config.get("server", {}).get("telegram", {})
        self.bot_token = tg_config.get("bot_token", "")
        self.allowed_chat_ids = set(tg_config.get("allowed_chat_ids", []))
        self.enabled = bool(self.bot_token)
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

    def is_allowed(self, chat_id: int) -> bool:
        """Check if a chat ID is allowed."""
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids

    def send_message(self, chat_id: int, text: str):
        """Send a Telegram message, splitting long messages if necessary."""
        if not self.enabled or not text:
            return

        chunks = split_telegram_message(text)

        for chunk in chunks:
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": chunk,
                            "parse_mode": "Markdown",
                        },
                    )
                    if resp.status_code != 200:
                        # Fallback to plain text if Markdown parsing fails
                        client.post(
                            f"{self.api_base}/sendMessage",
                            json={"chat_id": chat_id, "text": chunk},
                        )
            except Exception as e:
                print(f"[Forge] Telegram send failed: {e}")

    def parse_incoming(self, data: dict) -> tuple[int, str]:
        """Parse incoming Telegram update. Returns (chat_id, message_text)."""
        msg = data.get("message") or data.get("edited_message") or {}
        chat_id = msg.get("chat", {}).get("id", 0)
        text = msg.get("text", "").strip()
        return chat_id, text

    def setup_webhook(self, webhook_url: str) -> bool:
        """Register webhook URL with Telegram."""
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.api_base}/setWebhook",
                    json={"url": f"{webhook_url}/webhook/telegram"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def delete_webhook(self) -> bool:
        """Delete webhook to enable long polling mode."""
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{self.api_base}/deleteWebhook")
                return resp.status_code == 200
        except Exception:
            return False

    def poll_updates(
        self,
        on_message: Callable[[int, str], None],
        stop_event: threading.Event | None = None,
    ):
        """Long poll updates from Telegram (completely free, no public URL/ngrok required)."""
        if not self.enabled:
            return

        self.delete_webhook()
        offset = 0

        while stop_event is None or not stop_event.is_set():
            try:
                with httpx.Client(timeout=35) as client:
                    resp = client.get(
                        f"{self.api_base}/getUpdates",
                        params={"offset": offset, "timeout": 20},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for update in updates:
                            offset = update["update_id"] + 1
                            chat_id, text = self.parse_incoming(update)
                            if chat_id and text:
                                on_message(chat_id, text)
                    else:
                        time.sleep(3)
            except Exception:
                time.sleep(2)


class WhatsAppHandler:
    """Handle WhatsApp messages via Twilio API."""

    def __init__(self, config: dict):
        wa_config = config.get("server", {}).get("whatsapp", {})
        self.account_sid = wa_config.get("account_sid", "")
        self.auth_token = wa_config.get("auth_token", "")
        self.from_number = wa_config.get("from_number", "")
        self.allowed_numbers = set(wa_config.get("allowed_numbers", []))
        self.enabled = bool(self.account_sid and self.auth_token and self.from_number)

    def is_allowed(self, from_number: str) -> bool:
        """Check if a number is allowed to send commands."""
        if not self.allowed_numbers:
            return True
        return from_number in self.allowed_numbers

    def send_message(self, to_number: str, body: str):
        """Send a WhatsApp message via Twilio REST API."""
        if not self.enabled:
            return

        if len(body) > 4000:
            body = body[:3900] + "\n\n... (truncated)"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

        try:
            with httpx.Client(timeout=30) as client:
                client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={"Body": body, "From": self.from_number, "To": to_number},
                )
        except Exception as e:
            print(f"[Forge] WhatsApp send failed: {e}")

    def parse_incoming(self, form_data: dict) -> tuple[str, str]:
        """Parse incoming Twilio webhook data."""
        return form_data.get("From", ""), form_data.get("Body", "").strip()

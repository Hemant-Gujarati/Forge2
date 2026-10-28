"""Configuration management for Forge CLI."""

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".forge"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
SESSIONS_DIR = CONFIG_DIR / "sessions"
DB_PATH = CONFIG_DIR / "forge.db"

DEFAULT_CONFIG = {
    "default_provider": "ollama",
    "safe_mode": True,  # Require approval for destructive operations (write, edit, delete, run_command, git_commit)
    "providers": {
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
        },
        "anthropic": {
            "api_key": "",
            "base_url": "https://api.anthropic.com",
            "default_model": "claude-sonnet-4-20250514",
        },
        "gemini": {
            "api_key": "",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-2.0-flash",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "default_model": "llama3.2",
        },
    },
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "pairing_token": "",  # Secret token for pairing remote Android devices
        "whatsapp": {
            "account_sid": "",
            "auth_token": "",
            "from_number": "",
            "allowed_numbers": [],
        },
        "telegram": {
            "bot_token": "",
            "allowed_chat_ids": [],
        },
    },
}


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class Config:
    """Manages Forge configuration."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_FILE
        self.data: dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration from file or create default, applying env fallbacks."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                loaded = yaml.safe_load(f) or {}
            self.data = self._deep_merge(DEFAULT_CONFIG, loaded)
        else:
            self.data = self._deep_merge({}, DEFAULT_CONFIG)
            self.save()

        self._apply_env_fallbacks()

    def _apply_env_fallbacks(self):
        """Fill empty keys from environment variables if present."""
        providers = self.data.setdefault("providers", {})
        if not providers.get("openai", {}).get("api_key"):
            env_key = os.environ.get("OPENAI_API_KEY", "")
            if env_key:
                providers.setdefault("openai", {})["api_key"] = env_key

        if not providers.get("anthropic", {}).get("api_key"):
            env_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if env_key:
                providers.setdefault("anthropic", {})["api_key"] = env_key

        if not providers.get("gemini", {}).get("api_key"):
            env_key = os.environ.get("GEMINI_API_KEY", "")
            if env_key:
                providers.setdefault("gemini", {})["api_key"] = env_key

        server_tg = self.data.setdefault("server", {}).setdefault("telegram", {})
        if not server_tg.get("bot_token"):
            tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            if tg_token:
                server_tg["bot_token"] = tg_token

    def save(self):
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)

    def validate(self) -> list[str]:
        """Validate configuration settings and return list of warnings/issues."""
        issues = []
        # Check provider
        prov = self.default_provider
        providers = self.data.get("providers", {})
        if prov not in providers:
            issues.append(
                f"Default provider '{prov}' is not defined under providers in configuration."
            )

        # Check server settings
        server = self.data.get("server", {})
        port = server.get("port")
        if not isinstance(port, int) or port < 1 or port > 65535:
            issues.append(f"Invalid server port: {port}. Must be an integer between 1 and 65535.")

        tg = server.get("telegram", {})
        chat_ids = tg.get("allowed_chat_ids", [])
        if not isinstance(chat_ids, list):
            issues.append("server.telegram.allowed_chat_ids must be a list of integers.")

        return issues

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge override into a copy of base."""
        import copy

        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def get_provider_config(self, provider_name: str) -> dict:
        """Get configuration for a specific provider."""
        return self.data.get("providers", {}).get(provider_name, {})

    @property
    def default_provider(self) -> str:
        return self.data.get("default_provider", "ollama")

    @default_provider.setter
    def default_provider(self, value: str):
        self.data["default_provider"] = value

    @property
    def safe_mode(self) -> bool:
        """Whether destructive operations require user approval."""
        return bool(self.data.get("safe_mode", True))

    @safe_mode.setter
    def safe_mode(self, value: bool):
        self.data["safe_mode"] = bool(value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level config value."""
        return self.data.get(key, default)

    def set_api_key(self, target: str, api_key: str):
        """Set API key for a provider or service (e.g. telegram, openai)."""
        target_lower = target.lower()
        if target_lower == "telegram":
            self.data.setdefault("server", {}).setdefault("telegram", {})["bot_token"] = api_key
            self.save()
        elif target_lower == "whatsapp":
            self.data.setdefault("server", {}).setdefault("whatsapp", {})["auth_token"] = api_key
            self.save()
        elif target_lower == "pairing_token":
            self.data.setdefault("server", {})["pairing_token"] = api_key
            self.save()
        else:
            if target_lower not in self.data.get("providers", {}):
                self.data.setdefault("providers", {})[target_lower] = {
                    "api_key": api_key,
                    "base_url": "https://api.openai.com/v1",
                    "default_model": "gpt-4o",
                }
            else:
                self.data["providers"][target_lower]["api_key"] = api_key
            self.save()

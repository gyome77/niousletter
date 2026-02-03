from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv


@dataclass
class Settings:
    app_base_url: str
    timezone: str
    db_url: str
    retention_days: int
    gmail_sender_email: str
    gmail_credentials_json: str
    gmail_token_json: str
    summary_provider: str
    ollama_base_url: str
    ollama_model: str
    openai_api_key: str
    openai_model: str
    tracking_token_secret: str
    tracking_host: str
    tracking_port: int
    config_dir: Path


def load_settings() -> Settings:
    load_dotenv()

    app_base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8088")
    timezone = os.getenv("TIMEZONE", "UTC")
    db_url = os.getenv("DB_URL", "sqlite:////var/lib/newsletter-engine/newsletter.db")
    retention_days = int(os.getenv("RETENTION_DAYS", "45"))

    gmail_sender_email = os.getenv("GMAIL_SENDER_EMAIL", "")
    gmail_credentials_json = os.getenv("GMAIL_CREDENTIALS_JSON", "")
    gmail_token_json = os.getenv("GMAIL_TOKEN_JSON", "")

    summary_provider = os.getenv("SUMMARY_PROVIDER", "none").lower()
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    tracking_token_secret = os.getenv("TRACKING_TOKEN_SECRET", "")
    tracking_host = os.getenv("TRACKING_HOST", "127.0.0.1")
    tracking_port = int(os.getenv("TRACKING_PORT", "8088"))

    config_dir = Path(os.getenv("CONFIG_DIR", "config")).resolve()

    return Settings(
        app_base_url=app_base_url,
        timezone=timezone,
        db_url=db_url,
        retention_days=retention_days,
        gmail_sender_email=gmail_sender_email,
        gmail_credentials_json=gmail_credentials_json,
        gmail_token_json=gmail_token_json,
        summary_provider=summary_provider,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        tracking_token_secret=tracking_token_secret,
        tracking_host=tracking_host,
        tracking_port=tracking_port,
        config_dir=config_dir,
    )


def load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class ConfigLoader:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def load_groups(self) -> Dict[str, Any]:
        return load_json_file(self.config_dir / "groups.json")

    def load_sources(self) -> Dict[str, Any]:
        return load_json_file(self.config_dir / "sources.json")

    def load_templates(self) -> Dict[str, Any]:
        return load_json_file(self.config_dir / "templates.json")

    def load_newsletters(self) -> Dict[str, Any]:
        return load_json_file(self.config_dir / "newsletters.json")

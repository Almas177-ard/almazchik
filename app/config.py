"""Environment o'zgaruvchilari asosidagi konfiguratsiya (.env fayldan o'qiladi)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"


def _parse_ids(raw: str):
    out = set()
    for part in str(raw or "").replace(",", " ").split():
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return out


class Config:
    def __init__(self):
        self.bot_token: str = os.getenv("BOT_TOKEN", "").strip()
        if self.bot_token in {"", "1234567890:YOUR_BOT_TOKEN_HERE"}:
            self.bot_token = ""
        self.webapp_url: str = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
        if self.webapp_url.endswith("your-domain.example"):
            self.webapp_url = ""

        self.db_host: str = os.getenv("DB_HOST", "127.0.0.1")
        try:
            self.db_port: int = int(os.getenv("DB_PORT", "3306"))
        except ValueError:
            self.db_port = 3306
        self.db_user: str = os.getenv("DB_USER", "root")
        self.db_password: str = os.getenv("DB_PASSWORD", "")
        self.db_name: str = os.getenv("DB_NAME", "hamyon")

        self.web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
        try:
            self.web_port: int = int(os.getenv("WEB_PORT", "8000"))
        except ValueError:
            self.web_port = 8000

        self.admin_ids = _parse_ids(os.getenv("ADMIN_IDS", ""))
        self.secret_key: str = os.getenv("SECRET_KEY", "").strip()

    @property
    def session_secret(self) -> str:
        """Session tokenlarni imzolash uchun maxfiy kalit."""
        return self.secret_key or self.bot_token or "hamyon-dev-secret"


CFG = Config()

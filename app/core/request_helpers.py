import os
import re
import uuid
from typing import Optional

from fastapi import Request

from app.config import INTERNAL_API_KEY, PLATFORM_ADMIN_CHAT_ID, PLATFORM_BOT_TOKEN


def require_internal_api_key(
    x_api_key: Optional[str],
    authorization: Optional[str],
) -> bool:
    header_key = x_api_key or ""
    if not header_key and authorization:
        m = re.match(r"^Bearer\s+(.+)$", authorization, re.I)
        if m:
            header_key = m.group(1)
    return bool(INTERNAL_API_KEY) and header_key == INTERNAL_API_KEY


def generate_webhook_secret() -> str:
    return f"tg_{uuid.uuid4().hex}"


def build_bot_webhook_url(origin: str, bot_id: str) -> str:
    return f"{origin.rstrip('/')}/webhook/{bot_id}"


def get_platform_bot_token() -> str:
    return PLATFORM_BOT_TOKEN


def get_platform_admin_chat_id() -> int:
    return PLATFORM_ADMIN_CHAT_ID


def get_request_origin(request: Request) -> str:
    # Codespace / 反代环境下，request.base_url 可能带内部端口 :8000
    # Telegram webhook 只允许 80/88/443/8443，所以必须优先使用 .env 里的 BASE_URL
    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
    if base_url:
        return base_url
    return str(request.base_url).rstrip("/")

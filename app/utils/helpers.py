import re
import time
import uuid
import html
from datetime import datetime
from typing import Optional, Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import PLATFORM_ADMIN_CHAT_ID, PLATFORM_SECONDARY_ADMIN_CHAT_IDS


def cost_ms(start_ts: float) -> int:
    return int((time.perf_counter() - start_ts) * 1000)

def now_ms() -> int:
    return int(time.time() * 1000)

def safe_json_dumps(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return repr(data)

def sanitize_tenant_id(input_text: str = "") -> str:
    return re.sub(r"[^a-z0-9_-]", "_", str(input_text).strip().lower())

def format_date_ymd(ts_ms: Optional[int]) -> str:
    if not ts_ms:
        return "-"
    try:
        return datetime.fromtimestamp(int(ts_ms) / 1000).strftime("%Y-%m-%d")
    except Exception:
        return "-"

def is_primary_platform_admin(chat_id: int) -> bool:
    return int(chat_id) == int(PLATFORM_ADMIN_CHAT_ID)

def is_secondary_platform_admin(chat_id: int) -> bool:
    return int(chat_id) in PLATFORM_SECONDARY_ADMIN_CHAT_IDS

def build_bot_id_from_bot_username(bot_username: str) -> str:
    username = str(bot_username or "").strip().lstrip("@").lower()
    if not username:
        raise ValueError("bot_username_required")
    return sanitize_tenant_id(username)

def build_tenant_id_from_admin_chat_id(admin_chat_id: int) -> str:
    return f"tg_{int(admin_chat_id)}"

def escape_html(text: str = "") -> str:
    return html.escape(str(text), quote=False)

def mask_bot_token(token: str = "") -> str:
    s = str(token)
    if len(s) <= 12:
        return "****"
    return f"{s[:8]}****{s[-4:]}"

def is_skip_text(text: str = "") -> bool:
    val = str(text).strip().lower()
    return val in {"skip", "跳过", "无", "没有"}

def get_today_ymd() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def is_same_ymd_ts_ms(ts_ms: Optional[int], ymd: str) -> bool:
    return format_date_ymd(ts_ms) == ymd

def generate_webhook_secret() -> str:
    return f"tg_{uuid.uuid4().hex}"

def generate_apply_id() -> str:
    return f"apply_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

def build_bot_webhook_url(origin: str, bot_id: str) -> str:
    return f"{origin.rstrip('/')}/webhook/{bot_id}"

def get_request_origin(request: Request) -> str:
    return str(request.base_url).rstrip("/")

def build_user_link(user_id: int, username: str, display_name: str) -> str:
    safe_text = escape_html(display_name)
    return f'<a href="tg://user?id={user_id}">{safe_text}</a>'

def normalize_rate_action(action: str) -> str:
    s = str(action or "").strip().lower()
    return re.sub(r"[^a-z0-9:_-]", "_", s) or "unknown"


def json_response(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status)

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy = ROOT / "legacy" / "legacy_main.py"

if not legacy.exists():
    raise SystemExit("❌ 找不到 legacy/legacy_main.py，请先把原单文件放进去")

text = legacy.read_text(encoding="utf-8")

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"✅ wrote {path.relative_to(ROOT)}")

# 1. config.py：先不自动抽太狠，保留手写配置，避免破坏
config = r'''
import os

APP_NAME = "telegram-bot-multi-tenant-platform"

DEFAULT_WELCOME_TEXT = (
    "👋 请发信息与我沟通，我会尽快回复你！\n\n"
)

DEFAULT_FIRST_ACK_TEXT = "✅ 信息发送成功，请等待回复。"

DEFAULT_PLATFORM_WELCOME_TEXT = (
    "👋 欢迎使用机器人接入平台\n\n"
    "发送 /apply 开始接入机器人\n"
    "发送 /my 查看你名下机器人"
)

RATE_LIMIT_SINGLE_SECONDS = 2
RATE_LIMIT_BURST_WINDOW_SECONDS = 20
RATE_LIMIT_BURST_MAX_TIMES = 15
RATE_LIMIT_MUTE_SECONDS = 60 * 2
START_ALERT_WINDOW_SECONDS = 60 * 10
START_ALERT_THRESHOLD = 20
START_ALERT_COOLDOWN_SECONDS = 60 * 10

RATE_LIMIT_SINGLE_MSG = "频率过快，请稍后重试！"
RATE_LIMIT_MUTE_MSG = "请求过快，请休息2分钟再试"

LOCK_TTL_SECONDS = 600
FIRST_ACK_TTL_SECONDS = 60 * 60 * 24 * 30
STARTED_TTL_SECONDS = 60 * 60
APPLY_SESSION_TTL_SECONDS = 60 * 30
APPLY_RECORD_TTL_SECONDS = 60 * 60 * 24 * 30
DUPLICATE_UPDATE_TTL_SECONDS = 60 * 10
MESSAGE_MAP_TTL_SECONDS = 60 * 60 * 24 * 7

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
PLATFORM_BOT_TOKEN = os.getenv("PLATFORM_BOT_TOKEN", "").strip()
PLATFORM_ADMIN_CHAT_ID = int(os.getenv("PLATFORM_ADMIN_CHAT_ID", "0") or 0)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
BASE_URL = os.getenv("BASE_URL", "").strip()

PLATFORM_SECONDARY_ADMIN_CHAT_IDS = {
    int(x.strip())
    for x in os.getenv("PLATFORM_SECONDARY_ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
}
'''
write(ROOT / "app" / "config.py", config)

# 2. helpers.py：抽取无副作用工具函数
helper_names = [
    "cost_ms",
    "now_ms",
    "safe_json_dumps",
    "sanitize_tenant_id",
    "format_date_ymd",
    "is_primary_platform_admin",
    "is_secondary_platform_admin",
    "build_bot_id_from_bot_username",
    "build_tenant_id_from_admin_chat_id",
    "escape_html",
    "mask_bot_token",
    "is_skip_text",
    "get_today_ymd",
    "is_same_ymd_ts_ms",
    "generate_webhook_secret",
    "generate_apply_id",
    "build_bot_webhook_url",
    "get_request_origin",
    "build_user_link",
    "normalize_rate_action",
]

blocks = []
for name in helper_names:
    m = re.search(rf"\ndef {name}\(.*?(?=\n(?:async\s+)?def |\nclass |\n# =+|\Z)", text, re.S)
    if m:
        blocks.append(m.group(0).strip())

helpers = '''import re
import time
import uuid
import html
from datetime import datetime
from typing import Optional, Any

from fastapi import Request

from app.config import PLATFORM_ADMIN_CHAT_ID, PLATFORM_SECONDARY_ADMIN_CHAT_IDS
''' + "\n\n" + "\n\n".join(blocks) + "\n"
write(ROOT / "app" / "utils" / "helpers.py", helpers)

# 3. security.py
m = re.search(r"\ndef require_internal_api_key\(.*?(?=\n(?:async\s+)?def |\nclass |\n# =+|\Z)", text, re.S)
security_body = m.group(0).strip() if m else ""
security = '''import re
from typing import Optional

from app.config import INTERNAL_API_KEY

''' + security_body + "\n"
write(ROOT / "app" / "utils" / "security.py", security)

print("✅ step1 done")

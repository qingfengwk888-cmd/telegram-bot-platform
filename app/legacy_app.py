import os
import logging
from typing import Optional

from fastapi import FastAPI, Header, Request
from app.utils.helpers import (
    now_ms,
    json_response,
    sanitize_tenant_id,
    is_primary_platform_admin,
    is_secondary_platform_admin,
)
from app.core.lifespan import lifespan
from app.services.notice_service import (
    get_platform_notice_target,
)
from app.services.apply_service import (
    load_apply,
    get_apply_index,
)
from app.services.tenant_service import (
    load_tenant,
    save_tenant,
    get_tenant_index,
    set_platform_tenant_blacklisted,
)
from app.routes.health import router as health_router
from app.routes.platform import router as platform_router
from app.routes.webhook import router as webhook_router
from app.routes.internal import router as internal_router
from app.telegram.api import (
    tg,
    telegram_raw,
)

# ============================================================
# Config
# ============================================================

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
# 原 JS 中是 0，Cloudflare KV 的语义并不适合直接照搬。
# 这里改成永久记录“已经 start 过”，避免重复欢迎。
STARTED_TTL_SECONDS = 60 * 60
APPLY_SESSION_TTL_SECONDS = 60 * 30
APPLY_RECORD_TTL_SECONDS = 60 * 60 * 24 * 30
DUPLICATE_UPDATE_TTL_SECONDS = 60 * 10
MESSAGE_MAP_TTL_SECONDS = 60 * 60 * 24 * 7

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
PLATFORM_BOT_TOKEN = os.getenv("PLATFORM_BOT_TOKEN", "").strip()
PLATFORM_ADMIN_CHAT_ID = int(os.getenv("PLATFORM_ADMIN_CHAT_ID", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

PLATFORM_ADMIN_CHAT_ID = int(os.getenv("PLATFORM_ADMIN_CHAT_ID", "0"))
PLATFORM_SECONDARY_ADMIN_CHAT_IDS = {
    int(x.strip())
    for x in os.getenv("PLATFORM_SECONDARY_ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
}

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(APP_NAME)

# redis_client 已由 app.storage.redis_compat 提供
# telegram_http_client 已迁移到 app.telegram.api




app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.include_router(health_router)
app.include_router(platform_router)
app.include_router(webhook_router)
app.include_router(internal_router)




from app.core.request_helpers import (
    build_bot_webhook_url,
    get_platform_bot_token,
    get_request_origin,
    require_internal_api_key,
)


















from app.services.bot_callback_context_service import build_bot_callback_context
from app.services.bot_callback_dispatch_service import dispatch_bot_callback
from app.services.platform_callback_dispatch_service import dispatch_platform_callback
from app.services.platform_message_dispatch_service import dispatch_platform_message
from app.services.platform_blacklist_command_service import try_handle_platform_blacklist_command

# ============================================================
# Helpers
# ============================================================









































































































# ============================================================
# Tenant user/admin handlers
# ============================================================








# ============================================================
# Internal API
# ============================================================










# ============================================================
# Entrypoint
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

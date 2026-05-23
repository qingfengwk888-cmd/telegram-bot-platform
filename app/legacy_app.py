import os
import re
import json
import time
import uuid
import html
import logging
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from app.telegram.api import (
    tg,
    telegram_raw,
    register_bot_commands,
    register_bot_commands_safe,
    set_telegram_http_client,
)
from app.telegram.formatters import (
    format_button_preview,
    format_all_tenants_text,
    format_tenant_summary_text,
    format_started_users_text,
    format_tenant_category_text,
    build_apply_summary,
    build_creator_signature,
    build_final_welcome_text,
)
from app.telegram.keyboards import (
    build_bot_pick_buttons,
    build_my_bots_action_buttons,
    build_button_flow_action_buttons,
    build_global_broadcast_confirm_buttons,
    build_global_broadcast_target_buttons,
    build_modify_confirm_buttons,
    build_my_bots_entry_buttons,
    build_single_bot_action_buttons,
    build_button_manage_menu_buttons,
    build_button_delete_pick_buttons,
    build_button_reply_map,
    build_profile_buttons,
    flatten_welcome_buttons,
    rebuild_button_rows,
    build_remove_confirm_buttons,
    build_platform_reply_keyboard_for_admin,
    build_bot_reply_keyboard,
    build_platform_ad_menu_buttons,
    build_platform_ad_pick_buttons,
    build_platform_reply_keyboard_for_tenant,
    build_admin_tenant_pick_buttons,
    build_admin_tenant_root_menu_buttons,
    build_admin_tenant_traffic_sort_buttons,
    build_admin_tenant_category_buttons,
    build_admin_tenant_pick_buttons_with_back,
    build_tenant_category_buttons,
    build_tenant_detail_category_buttons,
    build_tenant_detail_action_buttons,
    build_new_tenant_notice_buttons,
    build_apply_approve_buttons,
    build_welcome_buttons,
)
from app.storage.redis_compat import redis_client

from app.storage.repository import (
    redis_get_json_db,
    redis_set_json_db,
    load_tenant_db,
    save_tenant_db,
    load_bot_db,
    save_bot_db,
    load_tenant_by_admin_chat_id_db,
    get_tenant_index_db,
    get_bot_index_db,
    list_bot_ids_by_tenant_id_db,
    list_bots_by_tenant_id_db,
    list_started_users_by_tenant_id_db,
    list_started_users_by_bot_id_db,
    save_started_user_profile_db,
    refresh_tenant_today_started_user_count_db,
    get_latest_bot_id_by_tenant_id_db,
    set_platform_tenant_blacklisted_db,
    is_platform_tenant_blacklisted_db,
    set_bot_user_blacklisted_db,
    is_bot_user_blacklisted_db,
    list_bot_blacklisted_users_db,
)

from datetime import datetime
from collections import OrderedDict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, Request

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

app = FastAPI(title=APP_NAME)
# redis_client 已由 app.storage.redis_compat 提供
# telegram_http_client 已迁移到 app.telegram.api



@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_http_client

    telegram_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    set_telegram_http_client(telegram_http_client)

    base_url = os.getenv("BASE_URL", "").strip()

    if not base_url:
        logger.info("BASE_URL not set, skip platform webhook setup")
    elif not PLATFORM_BOT_TOKEN:
        logger.info("PLATFORM_BOT_TOKEN not set, skip platform webhook setup")
    else:
        try:
            result = await telegram_raw(
                PLATFORM_BOT_TOKEN,
                "setWebhook",
                {"url": f"{base_url}/platform/webhook"}
            )
            logger.info("platform webhook setup result: %s", result)
        except Exception:
            logger.exception("failed to auto setup platform webhook")

    try:
        yield
    finally:
        if telegram_http_client is not None:
            await telegram_http_client.aclose()
            telegram_http_client = None
            set_telegram_http_client(None)

app = FastAPI(title=APP_NAME, lifespan=lifespan)




# ============================================================
# Helpers
# ============================================================

def cost_ms(start_ts: float) -> int:
    return int((time.perf_counter() - start_ts) * 1000)


def now_ms() -> int:
    return int(time.time() * 1000)


def json_response(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status)

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

async def load_bot_by_bot_username(bot_username: str) -> Optional[dict]:
    bot_id = build_bot_id_from_bot_username(bot_username)
    return await load_bot(bot_id)

async def list_bots_by_tenant_id(tenant_id: str) -> List[dict]:
    start_ts = time.perf_counter()
    bots = await list_bots_by_tenant_id_db(tenant_id, include_deleted=False)
    logger.info(
        "perf list_bots_by_tenant_id tenant_id=%s loaded=%s cost_ms=%s source=db",
        tenant_id,
        len(bots),
        cost_ms(start_ts),
    )
    return bots


async def list_all_bots_by_tenant_id(tenant_id: str) -> List[dict]:
    start_ts = time.perf_counter()
    bots = await list_bots_by_tenant_id_db(tenant_id, include_deleted=True)
    logger.info(
        "perf list_all_bots_by_tenant_id tenant_id=%s loaded=%s cost_ms=%s source=db",
        tenant_id,
        len(bots),
        cost_ms(start_ts),
    )
    return bots


async def list_started_users_by_tenant_id_for_admin(tenant_id: str) -> List[dict]:
    started = time.perf_counter()
    users = await list_started_users_by_tenant_id_db(tenant_id, include_deleted_bots=True)
    logger.info(
        "perf list_started_users_by_tenant_id_for_admin tenant_id=%s users=%s cost_ms=%s source=db",
        tenant_id,
        len(users),
        cost_ms(started),
    )
    return users


def get_today_ymd() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_same_ymd_ts_ms(ts_ms: Optional[int], ymd: str) -> bool:
    return format_date_ymd(ts_ms) == ymd


async def incr_bot_stat(bot_id: str, field: str, delta: int) -> None:
    if not bot_id or not delta:
        return

    lock_key = bot_stat_lock_key(bot_id)

    locked = False
    for _ in range(5):
        locked = await acquire_short_lock(lock_key, ttl=3)
        if locked:
            break
        await asyncio.sleep(0.05)

    if not locked:
        logger.warning("skip incr_bot_stat due to lock contention bot_id=%s field=%s delta=%s", bot_id, field, delta)
        return

    try:
        bot = await load_bot(bot_id)
        if not bot:
            return

        current = int(bot.get(field) or 0)
        next_value = current + int(delta)
        if next_value < 0:
            next_value = 0

        bot[field] = next_value
        bot["updatedAt"] = now_ms()
        await save_bot(bot)
    finally:
        await release_short_lock(lock_key)

        async def incr_tenant_stat(tenant_id: str, field: str, delta: int) -> None:
            if not tenant_id or not delta:
                return

            lock_key = tenant_stat_lock_key(tenant_id)

            locked = False
            for _ in range(5):
                locked = await acquire_short_lock(lock_key, ttl=3)
                if locked:
                    break
                await asyncio.sleep(0.05)

            if not locked:
                logger.warning(
                    "skip incr_tenant_stat due to lock contention tenant_id=%s field=%s delta=%s",
                    tenant_id,
                    field,
                    delta,
                )
                return

            try:
                tenant = await load_tenant(tenant_id)
                if not tenant:
                    return

                current = int(tenant.get(field) or 0)
                next_value = current + int(delta)
                if next_value < 0:
                    next_value = 0

                tenant[field] = next_value
                tenant["updatedAt"] = now_ms()
                await save_tenant(tenant)
            finally:
                await release_short_lock(lock_key)

async def incr_tenant_stat(tenant_id: str, field: str, delta: int) -> None:
    if not tenant_id or not delta:
        return

    lock_key = tenant_stat_lock_key(tenant_id)

    locked = False
    for _ in range(5):
        locked = await acquire_short_lock(lock_key, ttl=3)
        if locked:
            break
        await asyncio.sleep(0.05)

    if not locked:
        logger.warning(
            "skip incr_tenant_stat due to lock contention tenant_id=%s field=%s delta=%s",
            tenant_id,
            field,
            delta,
        )
        return

    try:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            return

        current = int(tenant.get(field) or 0)
        next_value = current + int(delta)
        if next_value < 0:
            next_value = 0

        tenant[field] = next_value
        tenant["updatedAt"] = now_ms()
        await save_tenant(tenant)
    finally:
        await release_short_lock(lock_key)


async def recompute_tenant_today_started_user_count(tenant_id: str) -> None:
    await refresh_tenant_today_started_user_count_db(tenant_id)


def tenant_started_users_key(tenant_id: str) -> str:
    return f"t:{tenant_id}:started_users"


def generate_webhook_secret() -> str:
    return f"tg_{uuid.uuid4().hex}"


def generate_apply_id() -> str:
    return f"apply_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


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


def build_user_link(user_id: int, username: str, display_name: str) -> str:
    safe_text = escape_html(display_name)
    return f'<a href="tg://user?id={user_id}">{safe_text}</a>'


















def find_bot_button_reply(bot: dict, incoming_text: str) -> Optional[str]:
    incoming_text = str(incoming_text or "").strip()
    if not incoming_text:
        return None

    reply_map = bot.get("welcomeButtonReplyMap") or {}
    reply = str(reply_map.get(incoming_text) or "").strip()
    if reply:
        return reply

    # 兼容老数据，兜底回退
    buttons = bot.get("welcomeButtons") or []
    for row in buttons:
        if not isinstance(row, list):
            continue
        for btn in row:
            if not isinstance(btn, dict):
                continue
            btn_text = str(btn.get("text") or "").strip()
            btn_reply = str(btn.get("reply") or "").strip()
            if btn_text and incoming_text == btn_text and btn_reply:
                return btn_reply

    return None

def is_plain_user_text_message(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return False

    # 命令不是普通消息
    if text.startswith("/"):
        return False

    # 这里如果你后续还有菜单关键词，也可以继续排除
    # 比如某些固定功能入口词：
    special_actions = {
        "帮助",
        "菜单",
        "开始",
    }
    if text in special_actions:
        return False

    return True

def classify_message_action(text: str, bot: dict) -> str:
    text = str(text or "").strip()

    if not text:
        return "empty"

    if text.startswith("/"):
        return f"command:{text.split()[0].lower()}"

    reply = find_bot_button_reply(bot, text)
    if reply:
        return f"button_reply:{normalize_rate_action(text)}"

    special_actions = {
        "帮助": "action:help",
        "菜单": "action:menu",
        "开始": "action:start",
    }
    if text in special_actions:
        return special_actions[text]

    return "plain_text"

def classify_platform_action(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return "empty"

    if text.startswith("/"):
        return f"platform_command:{text.split()[0].lower()}"

    special_actions = {
        "📝 添加机器人": "platform_action:apply",
        "📁 我的机器人": "platform_action:my_bots",
        "💬 帮助中心": "platform_action:help",
        "🇨🇳 切换中文包": "platform_action:switch_lang",
    }
    return special_actions.get(text, "platform_plain_text")



def format_simple_tenant_list_text(title: str, tenants: List[dict]) -> str:
    lines = [title, ""]

    if not tenants:
        lines.append("当前暂无租户。")
        return "\n".join(lines)

    lines.append(f"共 {len(tenants)} 个租户")
    lines.append("请选择一个租户查看详情：")
    return "\n".join(lines)

async def build_platform_dashboard_text() -> str:
    tenant_ids = await get_tenant_index()

    deleted_tenants = 0
    total_tenants = 0
    active_tenants = 0
    blacklisted_tenants = 0

    category_counts = {
        "local": 0,
        "external": 0,
        "other": 0,
        "blacklisted": 0,
    }

    total_started_users = 0
    today_started_users = 0
    recent_tenants = []


    for tenant_id in tenant_ids:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            continue

        status = str(tenant.get("status") or "active")
        if status == "deleted":
            deleted_tenants += 1
            total_tenants += 1
            continue

        total_tenants += 1

        if tenant.get("isBlacklisted"):
            blacklisted_tenants += 1
            category_counts["blacklisted"] += 1
        else:
            active_tenants += 1

            category = str(tenant.get("category") or "other")
            if category not in {"local", "external", "other"}:
                category = "other"
            category_counts[category] += 1

        bots = await list_bots_by_tenant_id(tenant_id)

        total_started_users += int(tenant.get("startedUserCount") or 0)
        today_started_users += int(tenant.get("todayStartedUserCount") or 0)


        recent_bot_username = ""
        if bots:
            latest_bot = max(
                bots,
                key=lambda x: int(x.get("createdAt") or 0)
            )
            recent_bot_username = str(((latest_bot.get("botInfo") or {}).get("username") or "")).strip()

        latest_bot_created_at = 0
        if bots:
            latest_bot_created_at = int(latest_bot.get("createdAt") or 0)

        recent_tenants.append({
            "tenantId": tenant_id,
            "tenantName": tenant.get("tenantName") or tenant_id,
            "botUsername": recent_bot_username,
            "creatorUsername": str(tenant.get("creatorUsername") or "").strip().lstrip("@"),
            "adminChatId": int(tenant.get("adminChatId") or 0),
            "createdAt": latest_bot_created_at or int(tenant.get("createdAt") or 0),
        })

    recent_tenants.sort(key=lambda x: x["createdAt"], reverse=True)

    lines = [
        "📊 <b>平台数据概览</b>",
        "",
        f"🏢 总租户数：<b>{total_tenants}</b>",
        f"✅ 正常租户：<b>{active_tenants}</b>",
        f"⛔ 拉黑租户：<b>{blacklisted_tenants}</b>",
        f"🗑 已删除租户：<b>{deleted_tenants}</b>",
        "",
        f"👥 总启动用户数：<b>{total_started_users}</b>",
        f"🆕 今日新增启动用户：<b>{today_started_users}</b>",
        "",
        "📂 分类统计：",
        f"• 招商(本)：<b>{category_counts['local']}</b>",
        f"• 招商(外)：<b>{category_counts['external']}</b>",
        f"• 其他：<b>{category_counts['other']}</b>",
        f"• 已拉黑：<b>{category_counts['blacklisted']}</b>",
        "",
        "🕘 最近接入租户：",
    ]

    if recent_tenants:
        for idx, item in enumerate(recent_tenants[:5], start=1):
            tenant_name = str(item["tenantName"]).strip()
            bot_username = str(item["botUsername"]).strip()
            creator_username = str(item.get("creatorUsername") or "").strip().lstrip("@")
            admin_chat_id = int(item.get("adminChatId") or 0)
            created_date = format_date_ymd(item["createdAt"])

            tenant_link = ""
            if creator_username:
                tenant_link = f"https://t.me/{creator_username}"
            elif admin_chat_id:
                tenant_link = f"tg://user?id={admin_chat_id}"

            bot_link = f"https://t.me/{bot_username}" if bot_username else ""

            tenant_title = (
                f'<a href="{tenant_link}"><b>{escape_html(tenant_name)}</b></a>'
                if tenant_link else
                f"<b>{escape_html(tenant_name)}</b>"
            )

            bot_title = (
                f'<a href="{bot_link}">@{escape_html(bot_username)}</a>'
                if bot_link else
                "未获取"
            )

            lines.append(
                f"{idx}. {tenant_title} | {bot_title} | {created_date}"
            )
    else:
        lines.append("暂无租户数据")

    return "\n".join(lines)



def is_new_tenant_notice_text(text: str) -> bool:
    text = str(text or "")
    return (
        "🟢 有新租户加入" in text
        or "🟢 <b>有新租户加入</b>" in text
        or "🟢 有新机器人接入" in text
        or "🟢 <b>有新机器人接入</b>" in text
    )



async def refresh_tenant_detail_message(
    *,
    platform_bot_token: str,
    message: dict,
    tenant: dict,
    from_id: int,
) -> None:
    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return

    tenant_id = str(tenant.get("tenantId") or "").strip()
    original_text = str(message.get("text") or "")

    # 1) 如果当前消息是“新租户/新机器人接入通知”页，只刷新按钮状态，不改正文
    if is_new_tenant_notice_text(original_text):
        await tg(platform_bot_token, "editMessageReplyMarkup", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "reply_markup": build_new_tenant_notice_buttons(tenant),
        })
        return

    # 2) 如果当前消息是租户详情页，刷新正文 + 按钮
    bots = await list_bots_by_tenant_id(tenant_id)
    users = await list_started_users_by_tenant_id_for_admin(tenant_id)

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": (
            (await format_tenant_summary_text(tenant, bots))
            + "\n\n"
            + format_started_users_text(tenant, users)
            + "\n\n"
            + format_tenant_category_text(tenant)
        ),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": build_tenant_detail_action_buttons(tenant_id, from_id),
    })


async def notify_new_bot_connected(
    *,
    platform_bot_token: str,
    platform_admin_chat_id: int,
    tenant_id: str,
    tenant_name: str,
    chat_id: int,
    username: str,
    display_name: str,
    bot: dict,
) -> None:
    try:
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        user_link = build_user_link(int(chat_id), username, display_name)

        notice_text = (
            "🟢 <b>新机器人接入</b>\n"
            "━━━━━━━━━━\n"
            f"👤 租户用户：{user_link}\n"
            f'💬 Chat ID：<a href="tg://user?id={chat_id}"><code>{chat_id}</code></a>\n'
            f"🏢 租户名称：<b>{escape_html(tenant_name)}</b>\n"
            f"🤖 机器人：<b>{escape_html('@' + bot_username)}</b>"
        )

        reply_markup = {
            "inline_keyboard": build_tenant_category_buttons(tenant_id)
        }

        if platform_admin_chat_id:
            try:
                notify_res = await tg(platform_bot_token, "sendMessage", {
                    "chat_id": platform_admin_chat_id,
                    "text": notice_text,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup,
                })

                if notify_res.get("result", {}).get("message_id"):
                    await map_platform_notice_message(
                        int(notify_res["result"]["message_id"]),
                        tenant_id,
                        chat_id,
                    )
            except Exception:
                logger.exception(
                    "notify primary platform admin failed tenant_id=%s chat_id=%s",
                    tenant_id,
                    platform_admin_chat_id,
                )

        for secondary_chat_id in PLATFORM_SECONDARY_ADMIN_CHAT_IDS:
            try:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": secondary_chat_id,
                    "text": notice_text,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup,
                })
            except Exception:
                logger.exception(
                    "notify secondary platform admin failed tenant_id=%s chat_id=%s",
                    tenant_id,
                    secondary_chat_id,
                )
    except Exception:
        logger.exception("notify_new_bot_connected task failed")






def bot_stat_lock_key(bot_id: str) -> str:
    return f"lock:bot:stat:{bot_id}"

def tenant_stat_lock_key(tenant_id: str) -> str:
    return f"lock:tenant:stat:{tenant_id}"

async def acquire_short_lock(key: str, ttl: int = 3) -> bool:
    return bool(await redis_client.set(key, "1", ex=ttl, nx=True))

async def release_short_lock(key: str) -> None:
    await redis_client.delete(key)


def bot_started_users_key(bot_id: str) -> str:
    return f"b:{bot_id}:started_users"

def bot_user_profile_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:profile:{int(user_id)}"

def bot_user_black_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:black:user:{int(user_id)}"

def bot_user_blacklist_set_key(bot_id: str) -> str:
    return f"b:{bot_id}:black:users"

def bot_user_rate_action_key(bot_id: str, user_id: int, action: str) -> str:
    return f"b:{bot_id}:rate:action:{int(user_id)}:{action}"

def bot_user_rate_mute_notice_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:rate:mute_notice:{int(user_id)}"

def bot_user_rate_burst_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:rate:burst:{int(user_id)}"

def bot_user_rate_mute_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:rate:mute:{int(user_id)}"

def bot_start_alert_window_key(bot_id: str) -> str:
    return f"b:{bot_id}:start_alert:window"

def bot_start_alert_cooldown_key(bot_id: str) -> str:
    return f"b:{bot_id}:start_alert:cooldown"


async def save_started_user_profile(bot_id: str, user: dict) -> None:
    await save_started_user_profile_db(bot_id, user)


async def check_bot_start_alert(bot: dict, user_profile: dict) -> None:
    bot_id = sanitize_tenant_id(bot.get("botId") or "")
    if not bot_id:
        return

    started_at = int(user_profile.get("startedAt") or 0)
    if not started_at:
        return

    window_key = bot_start_alert_window_key(bot_id)
    cooldown_key = bot_start_alert_cooldown_key(bot_id)

    now_ts = int(time.time())
    window_start_ts = now_ts - START_ALERT_WINDOW_SECONDS

    await redis_client.zadd(window_key, {str(user_profile["userId"]): now_ts})
    await redis_client.zremrangebyscore(window_key, 0, window_start_ts - 1)

    started_count = int(await redis_client.zcard(window_key) or 0)

    if started_count <= START_ALERT_THRESHOLD:
        return

    cooldown_ok = await redis_client.set(
        cooldown_key,
        "1",
        ex=START_ALERT_COOLDOWN_SECONDS,
        nx=True,
    )
    if not cooldown_ok:
        return

    tenant_id = str(bot.get("tenantId") or "").strip()
    tenant_name = str(bot.get("tenantName") or tenant_id or bot_id).strip()
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    bot_show = f"@{bot_username}" if bot_username else bot_id

    text = (
        "⚠️ <b>启动异常预警</b>\n"
        "━━━━━━━━━━\n"
        f"🏢 租户：<b>{escape_html(tenant_name)}</b>\n"
        f"🆔 tenantId：<code>{escape_html(tenant_id)}</code>\n"
        f"🤖 机器人：<b>{escape_html(bot_show)}</b>\n"
        f"🆔 botId：<code>{escape_html(bot_id)}</code>\n"
        f"📈 近10分钟启动人数：<b>{started_count}</b>\n"
        "⚠️ 该机器人近10分钟启动人数过高，存在刷量风险。"
    )

    reply_markup = {
        "inline_keyboard": [[
            {"text": "查看租户详情", "callback_data": f"admin_tenant:view:{tenant_id}"}
        ]]
    }

    platform_bot_token = get_platform_bot_token()
    target_admin_ids = set()

    primary_admin_chat_id = get_platform_admin_chat_id()
    if primary_admin_chat_id:
        target_admin_ids.add(int(primary_admin_chat_id))

    for admin_id in PLATFORM_SECONDARY_ADMIN_CHAT_IDS:
        if admin_id:
            target_admin_ids.add(int(admin_id))

    for admin_id in target_admin_ids:
        try:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": admin_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            })
        except Exception:
            logger.exception(
                "notify start alert failed botId=%s chat_id=%s",
                bot_id,
                admin_id,
            )


async def pick_default_bot_for_tenant(tenant_id: str) -> Optional[dict]:
    latest_bot_id = await get_latest_bot_id_by_tenant_id_db(tenant_id)
    if not latest_bot_id:
        return None
    return await load_bot(latest_bot_id)


async def pick_sender_bot_for_tenant(tenant_id: str) -> Optional[dict]:
    return await pick_default_bot_for_tenant(tenant_id)


async def list_started_users_by_tenant_id(tenant_id: str) -> List[dict]:
    started = time.perf_counter()
    users = await list_started_users_by_tenant_id_db(tenant_id, include_deleted_bots=False)
    logger.info(
        "perf list_started_users_by_tenant_id tenant_id=%s users=%s cost_ms=%s source=db",
        tenant_id,
        len(users),
        cost_ms(started),
    )
    return users


async def list_started_users(bot_id: str) -> List[dict]:
    started = time.perf_counter()
    users = await list_started_users_by_bot_id_db(bot_id)
    logger.info(
        "perf list_started_users bot_id=%s users=%s cost_ms=%s source=db",
        bot_id,
        len(users),
        cost_ms(started),
    )
    return users




def tenant_latest_bot_id_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}:latest_bot_id"

async def refresh_tenant_latest_bot_id(tenant_id: str) -> None:
    # 数据库版不再需要单独维护 latest_bot_id key。
    # 最新 bot 通过 bots.created_at_ms 排序实时计算。
    return None


def tenant_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}"

def bot_key(bot_id: str) -> str:
    return f"bot:{bot_id}"

def bot_index_key() -> str:
    return "bot:index"

def tenant_bots_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}:bots"

def tenant_all_bots_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}:all_bots"


def tenant_index_key() -> str:
    return "tenant:index"


def tenant_data_key(tenant_id: str, *parts: Any) -> str:
    return ":".join(["t", tenant_id, *map(str, parts)])


def apply_key(apply_id: str) -> str:
    return f"apply:{apply_id}"

def platform_tenant_notice_map_key(message_id: int) -> str:
    return f"platform:tenant_notice_map:{int(message_id)}"

def platform_tenant_black_key(tenant_id: str) -> str:
    return f"platform:black:tenant:{sanitize_tenant_id(tenant_id)}"


async def map_platform_notice_message(message_id: int, tenant_id: str, applicant_chat_id: int) -> None:
    await redis_set_json(
        platform_tenant_notice_map_key(message_id),
        {
            "tenantId": sanitize_tenant_id(tenant_id),
            "applicantChatId": int(applicant_chat_id),
            "ts": now_ms(),
        },
        MESSAGE_MAP_TTL_SECONDS,
    )

async def get_platform_notice_target(message_id: int) -> Optional[dict]:
    return await redis_get_json(platform_tenant_notice_map_key(message_id))


async def set_platform_tenant_blacklisted(tenant_id: str, value: bool) -> None:
    await set_platform_tenant_blacklisted_db(tenant_id, value)


async def is_platform_tenant_blacklisted(tenant_id: str) -> bool:
    return await is_platform_tenant_blacklisted_db(tenant_id)


async def set_bot_user_blacklisted(bot_id: str, user_id: int, value: bool) -> None:
    await set_bot_user_blacklisted_db(bot_id, user_id, value)


async def is_bot_user_blacklisted(bot_id: str, user_id: int) -> bool:
    return await is_bot_user_blacklisted_db(bot_id, user_id)


async def is_tenant_user_blacklisted(tenant_id: str, user_id: int) -> bool:
    tenant_id = str(tenant_id or "").strip()
    user_id = int(user_id or 0)

    if not tenant_id or not user_id:
        return False

    bots = await list_bots_by_tenant_id(tenant_id)
    for bot in bots:
        bot_id = str(bot.get("botId") or "").strip()
        if not bot_id:
            continue

        if await is_bot_user_blacklisted(bot_id, user_id):
            return True

    return False

async def list_blacklisted_users_by_tenant_id(tenant_id: str) -> List[dict]:
    bots = await list_bots_by_tenant_id(tenant_id)
    results: List[dict] = []
    seen_user_ids = set()

    for bot in bots:
        bot_id = str(bot.get("botId") or "").strip()
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

        if not bot_id:
            continue

        users = await list_blacklisted_users(bot_id)
        for u in users:
            user_id = int(u.get("userId") or 0)
            if not user_id or user_id in seen_user_ids:
                continue

            seen_user_ids.add(user_id)
            results.append({
                **u,
                "botId": bot_id,
                "botUsername": str(u.get("botUsername") or bot_username).strip(),
                "tenantId": tenant_id,
            })

    return results




async def list_blacklisted_users(bot_id: str) -> List[dict]:
    return await list_bot_blacklisted_users_db(bot_id)


def format_blacklisted_users_text(bot: dict, users: List[dict]) -> str:
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    bot_show = f"@{bot_username}" if bot_username else (bot.get("botId") or "")
    tenant_name = str(bot.get("tenantName") or bot.get("tenantId") or "").strip()

    lines = [
        f"🚫 机器人 <b>{escape_html(bot_show)}</b> 黑名单",
        f"🏢 所属租户：<b>{escape_html(tenant_name)}</b>",
        f"总数：<b>{len(users)}</b>",
        ""
    ]

    for idx, u in enumerate(users[:100], start=1):
        username = str(u.get("username") or "").strip()
        first_name = str(u.get("firstName") or "").strip()
        last_name = str(u.get("lastName") or "").strip()
        user_id = int(u.get("userId"))

        display_name = (
            f"@{username}"
            if username else
            (" ".join([x for x in [first_name, last_name] if x]).strip() or f"UID:{user_id}")
        )

        lines.append(f"{idx}. {escape_html(display_name)} | UID:<code>{user_id}</code>")

    if len(users) > 100:
        lines.append("")
        lines.append(f"仅显示前 100 个，共 {len(users)} 个")

    if not users:
        lines.append("当前黑名单为空。")

    return "\n".join(lines)

def format_tenant_blacklisted_users_text(tenant: dict, users: List[dict]) -> str:
    tenant_name = str(tenant.get("tenantName") or tenant.get("tenantId") or "").strip()

    lines = [
        f"🚫 租户 <b>{escape_html(tenant_name)}</b> 黑名单汇总",
        f"总数：<b>{len(users)}</b>",
        ""
    ]

    for idx, u in enumerate(users[:100], start=1):
        username = str(u.get("username") or "").strip()
        first_name = str(u.get("firstName") or "").strip()
        last_name = str(u.get("lastName") or "").strip()
        user_id = int(u.get("userId") or 0)
        bot_username = str(u.get("botUsername") or "").strip()
        bot_show = f"@{bot_username}" if bot_username else "unknown_bot"

        display_name = (
            f"@{username}"
            if username else
            (" ".join([x for x in [first_name, last_name] if x]).strip() or f"UID:{user_id}")
        )

        lines.append(
            f"{idx}. {escape_html(display_name)} | UID:<code>{user_id}</code> | 机器人:<code>{escape_html(bot_show)}</code>"
        )

    if len(users) > 100:
        lines.append("")
        lines.append(f"仅显示前 100 个，共 {len(users)} 个")

    if not users:
        lines.append("当前黑名单为空。")

    return "\n".join(lines)




def apply_index_key() -> str:
    return "apply:index"


def apply_session_key(user_id: int) -> str:
    return f"apply:session:{user_id}"

def normalize_rate_action(action: str) -> str:
    s = str(action or "").strip().lower()
    return re.sub(r"[^a-z0-9:_-]", "_", s) or "unknown"


async def get_bot_user_rate_limit_status(
    bot_id: str,
    user_id: int,
    action: str,
) -> Dict[str, Any]:
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user_id)
    action = normalize_rate_action(action)

    mute_key = bot_user_rate_mute_key(bot_id, user_id)
    mute_notice_key = bot_user_rate_mute_notice_key(bot_id, user_id)
    action_key = bot_user_rate_action_key(bot_id, user_id, action)
    burst_key = bot_user_rate_burst_key(bot_id, user_id)

    # 1) 已在禁言中：只提示一次，后续静默拦截
    mute_ttl = await redis_client.ttl(mute_key)
    if mute_ttl and mute_ttl > 0:
        notice_sent = await redis_client.get(mute_notice_key)
        if notice_sent:
            return {
                "blocked": True,
                "reason": "muted",
                "message": "",
                "retry_after": mute_ttl,
            }

        await redis_client.set(
            mute_notice_key,
            "1",
            ex=max(int(mute_ttl), 1),
        )
        return {
            "blocked": True,
            "reason": "muted",
            "message": RATE_LIMIT_MUTE_MSG,
            "retry_after": mute_ttl,
        }

    # 2) 先累计 20 秒内总触发次数
    burst_count = await redis_client.incr(burst_key)
    if burst_count == 1:
        await redis_client.expire(burst_key, RATE_LIMIT_BURST_WINDOW_SECONDS)

    if burst_count > RATE_LIMIT_BURST_MAX_TIMES:
        await redis_client.set(
            mute_key,
            "1",
            ex=RATE_LIMIT_MUTE_SECONDS,
        )
        await redis_client.set(
            mute_notice_key,
            "1",
            ex=RATE_LIMIT_MUTE_SECONDS,
        )
        return {
            "blocked": True,
            "reason": "burst_too_many",
            "message": RATE_LIMIT_MUTE_MSG,
            "retry_after": RATE_LIMIT_MUTE_SECONDS,
        }

    # 3) 再做 3 秒同功能限流
    single_ok = await redis_client.set(
        action_key,
        "1",
        ex=RATE_LIMIT_SINGLE_SECONDS,
        nx=True,
    )
    if not single_ok:
        return {
            "blocked": True,
            "reason": "too_fast_same_action",
            "message": RATE_LIMIT_SINGLE_MSG,
            "retry_after": RATE_LIMIT_SINGLE_SECONDS,
        }

    return {
        "blocked": False,
        "reason": "",
        "message": "",
        "retry_after": 0,
    }

async def reply_rate_limited_for_callback(bot: dict, callback_query_id: str, text: str) -> None:
    await tg(bot["botToken"], "answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": True,
    })


async def reply_rate_limited_for_message(bot: dict, chat_id: int, text: str) -> None:
    await tg(bot["botToken"], "sendMessage", {
        "chat_id": chat_id,
        "text": text,
    })



# ============================================================
# Redis storage
# ============================================================

def platform_ad_config_key() -> str:
    return "platform:ad:config"


async def load_platform_ad_config() -> Optional[dict]:
    return await redis_get_json(platform_ad_config_key())


async def save_platform_ad_config(data: dict) -> None:
    await redis_set_json(platform_ad_config_key(), data)

def generate_ad_id() -> str:
    return f"ad_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

async def list_platform_ads() -> List[dict]:
    data = await load_platform_ad_config()
    items = (data or {}).get("items") or []
    if not isinstance(items, list):
        return []
    return items

async def get_platform_ad_by_id(ad_id: str) -> Optional[dict]:
    items = await list_platform_ads()
    for item in items:
        if str(item.get("adId") or "") == str(ad_id):
            return item
    return None

async def save_platform_ads(items: List[dict]) -> None:
    await save_platform_ad_config({"items": items})

async def delete_platform_ad_config() -> None:
    await redis_client.delete(platform_ad_config_key())


async def redis_get_json(key: str) -> Optional[dict]:
    return await redis_get_json_db(key)

async def redis_set_json(key: str, value: dict, ttl_seconds: Optional[int] = None) -> None:
    await redis_set_json_db(key, value, ttl_seconds)

async def load_tenant(tenant_id: str) -> Optional[dict]:
    return await load_tenant_db(tenant_id)

async def save_tenant(tenant: dict) -> None:
    await save_tenant_db(tenant)

async def load_bot(bot_id: str) -> Optional[dict]:
    return await load_bot_db(bot_id)

async def save_bot(bot: dict) -> None:
    await save_bot_db(bot)

async def load_tenant_by_admin_chat_id(admin_chat_id: int) -> Optional[dict]:
    return await load_tenant_by_admin_chat_id_db(admin_chat_id)

async def get_tenant_index() -> List[str]:
    return await get_tenant_index_db()


async def add_tenant_index(tenant_id: str) -> None:
    # 数据库版不需要维护 Redis tenant:index
    return None


async def remove_tenant_index(tenant_id: str) -> None:
    # 数据库版不需要维护 Redis tenant:index
    return None


async def get_bot_index() -> List[str]:
    return await get_bot_index_db()


async def add_bot_index(bot_id: str) -> None:
    # 数据库版不需要维护 Redis bot:index
    return None


async def remove_bot_index(bot_id: str) -> None:
    # 数据库版不需要维护 Redis bot:index
    return None


async def list_tenants_by_admin_chat_id(admin_chat_id: int) -> List[dict]:
    ids = await get_tenant_index()
    tenants: List[dict] = []
    for tenant_id in ids:
        tenant = await load_tenant(tenant_id)
        if (
            tenant
            and int(tenant.get("adminChatId", 0)) == int(admin_chat_id)
            and str(tenant.get("status") or "active") != "deleted"
        ):
            tenants.append(tenant)
    return tenants


async def load_apply(apply_id: str) -> Optional[dict]:
    return await redis_get_json(apply_key(apply_id))


async def save_apply(apply: dict) -> None:
    key = apply_key(apply["applyId"])
    await redis_set_json(key, apply, APPLY_RECORD_TTL_SECONDS)
    await redis_client.lrem(apply_index_key(), 0, apply["applyId"])
    await redis_client.lpush(apply_index_key(), apply["applyId"])


async def get_apply_index(limit: int = 100) -> List[str]:
    return await redis_client.lrange(apply_index_key(), 0, max(limit - 1, 0))


async def load_apply_session(user_id: int) -> Optional[dict]:
    return await redis_get_json(apply_session_key(user_id))


async def save_apply_session(user_id: int, session: dict) -> None:
    await redis_set_json(apply_session_key(user_id), session, APPLY_SESSION_TTL_SECONDS)


async def clear_apply_session(user_id: int) -> None:
    await redis_client.delete(apply_session_key(user_id))

def is_input_session(session: Optional[dict]) -> bool:
    if not session:
        return False

    mode = str(session.get("mode") or "")
    step = str(session.get("step") or "")

    if mode == "create" and step == "bot_token":
        return True

    if mode == "modify" and step in {
        "welcome_text_input",
        "button_text_input",
        "button_reply_input",
        "confirm_submit",
    }:
        return True

    if mode == "tenant_broadcast" and step in {
        "broadcast_input",
        "broadcast_confirm",
    }:
        return True

    if mode == "platform_ad_config" and step in {
        "ad_text_input",
        "ad_url_input",
    }:
        return True

    if mode == "admin_tenant_broadcast" and step in {
        "broadcast_input",
        "broadcast_confirm",
    }:
        return True

    if mode == "platform_global_broadcast" and step in {
        "broadcast_input",
        "broadcast_confirm",
    }:
        return True

    return False


async def interrupt_input_session_if_needed(
    user_id: int,
    session: Optional[dict],
    *,
    platform_bot_token: str,
    notify_chat_id: Optional[int] = None,
) -> Optional[dict]:
    if not is_input_session(session):
        return session

    await clear_apply_session(user_id)
    return None

def is_busy_input_session(session: Optional[dict]) -> bool:
    if not session:
        return False

    mode = str(session.get("mode") or "")
    step = str(session.get("step") or "")

    return (
        (mode == "create" and step == "bot_token")
        or (mode == "modify" and step in {
            "welcome_text_input",
            "button_text_input",
            "button_reply_input",
            "button_more_action",
            "modify_confirm",
        })
        or (mode == "tenant_broadcast" and step in {
            "broadcast_input",
            "broadcast_confirm",
        })
        or (mode == "platform_ad_config" and step in {
            "ad_text_input",
            "ad_url_input",
        })
        or (mode == "admin_tenant_broadcast" and step in {
            "broadcast_input",
            "broadcast_confirm",
        })
        or (mode == "platform_global_broadcast" and step in {
            "broadcast_input",
            "broadcast_confirm",
        })
    )


async def is_duplicate_update(scope: str, update_id: Optional[int]) -> bool:
    if update_id is None:
        return False
    key = f"dup:{scope}:{update_id}"
    result = await redis_client.set(key, "1", ex=DUPLICATE_UPDATE_TTL_SECONDS, nx=True)
    return result is None


async def set_current_lock(tenant_id: str, admin_chat_id: int, user_id: int) -> None:
    value = {"userId": int(user_id), "ts": now_ms()}
    await redis_set_json(
        tenant_data_key(tenant_id, "lock", admin_chat_id),
        value,
        LOCK_TTL_SECONDS,
    )


async def get_current_lock(tenant_id: str, admin_chat_id: int) -> Optional[int]:
    data = await redis_get_json(tenant_data_key(tenant_id, "lock", admin_chat_id))
    if not data or "userId" not in data:
        return None
    try:
        return int(data["userId"])
    except Exception:
        return None


async def refresh_lock_if_current(tenant_id: str, admin_chat_id: int, user_id: int) -> None:
    locked_user_id = await get_current_lock(tenant_id, admin_chat_id)
    if locked_user_id is not None and int(locked_user_id) == int(user_id):
        await set_current_lock(tenant_id, admin_chat_id, user_id)


# ============================================================
# Telegram API
# ============================================================


async def get_or_create_tenant_by_admin(
    admin_chat_id: int,
    username: str = "",
    display_name: str = "",
) -> dict:
    tenant_id = build_tenant_id_from_admin_chat_id(admin_chat_id)
    tenant = await load_tenant(tenant_id)

    if tenant:
        tenant["updatedAt"] = now_ms()
        if username:
            tenant["creatorUsername"] = username
        if display_name:
            tenant["creatorName"] = display_name

        if "startedUserCount" not in tenant:
            tenant["startedUserCount"] = 0
        if "todayStartedUserCount" not in tenant:
            tenant["todayStartedUserCount"] = 0

        await save_tenant(tenant)
        return tenant

    tenant_name = username or display_name or f"user_{admin_chat_id}"

    tenant = {
        "tenantId": tenant_id,
        "tenantName": tenant_name,
        "status": "active",
        "adminChatId": admin_chat_id,
        "creatorUsername": username or "",
        "creatorName": display_name or "",
        "createdAt": now_ms(),
        "updatedAt": now_ms(),
        "isBlacklisted": False,
        "category": "other",
        "startedUserCount": 0,
        "todayStartedUserCount": 0,
    }

    await save_tenant(tenant)
    return tenant

async def create_bot_from_payload(request: Request, payload: dict) -> dict:
    start_ts = time.perf_counter()

    bot_token = str(payload.get("botToken") or "").strip()
    admin_chat_id = int(payload.get("adminChatId") or 0)
    detail_url = str(payload.get("detailUrl") or "").strip()
    tenant_id = str(payload.get("tenantId") or "").strip()

    if not bot_token:
        raise ValueError("botToken_required")
    if not admin_chat_id:
        raise ValueError("adminChatId_required")
    if not tenant_id:
        raise ValueError("tenantId_required")

    bot_info = payload.get("botInfo") or {}
    if not bot_info:
        me = await telegram_raw(bot_token, "getMe", {})
        if not me.get("ok"):
            raise ValueError(f"bot_token_invalid: {json.dumps(me, ensure_ascii=False)}")
        bot_info = me.get("result") or {}

    bot_username = str(bot_info.get("username") or "").strip()
    bot_id = build_bot_id_from_bot_username(bot_username)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        raise ValueError("tenant_not_found")

    exists = await load_bot_by_bot_username(bot_username)
    if exists:
        exists_status = str(exists.get("status") or "active")

        if exists_status == "deleted":
            old_tenant_id = str(exists.get("tenantId") or "").strip()

            exists["status"] = "active"
            exists["deletedAt"] = 0
            exists["updatedAt"] = now_ms()
            exists["tenantId"] = tenant_id
            exists["tenantName"] = tenant.get("tenantName") or payload.get("tenantName") or tenant_id
            exists["adminChatId"] = admin_chat_id
            exists["botToken"] = bot_token
            exists["botInfo"] = bot_info
            exists["isBlacklisted"] = False
            exists["creatorUsername"] = payload.get("creatorUsername") or exists.get("creatorUsername") or ""
            exists["creatorName"] = payload.get("creatorName") or exists.get("creatorName") or ""

            if "startedUserCount" not in exists:
                exists["startedUserCount"] = 0
            if "blacklistedUserCount" not in exists:
                exists["blacklistedUserCount"] = 0

            hook_url = build_bot_webhook_url(get_request_origin(request), bot_id)
            result = await telegram_raw(
                bot_token,
                "setWebhook",
                {
                    "url": hook_url,
                    "secret_token": exists["webhookSecret"],
                },
            )

            if not result.get("ok"):
                raise RuntimeError(f"set_webhook_failed: {json.dumps(result, ensure_ascii=False)}")

            if old_tenant_id and old_tenant_id != tenant_id:
                pass

            await save_bot(exists)

            asyncio.create_task(register_bot_commands_safe(bot_token))

            logger.info(
                "perf onboarding bot_id=%s phase=restore total_cost_ms=%s",
                bot_id,
                cost_ms(start_ts),
            )

            return {
                "tenant": tenant,
                "bot": exists,
                "webhook": {
                    "url": hook_url,
                    "secretToken": exists["webhookSecret"],
                },
                "telegram": result,
            }

        raise ValueError("tenant_already_exists")

    bot = {
        "botId": bot_id,
        "tenantId": tenant_id,
        "tenantName": tenant.get("tenantName") or tenant_id,
        "status": payload.get("status") or "active",
        "botToken": bot_token,
        "adminChatId": admin_chat_id,
        "detailUrl": detail_url,
        "detailButtonText": payload.get("detailButtonText") or "👉 了解详情",
        "welcomeText": payload.get("welcomeText") or DEFAULT_WELCOME_TEXT,
        "welcomeButtons": payload.get("welcomeButtons") or [],
        "firstAckText": payload.get("firstAckText") or DEFAULT_FIRST_ACK_TEXT,
        "creatorUsername": payload.get("creatorUsername") or "",
        "creatorName": payload.get("creatorName") or "",
        "webhookSecret": payload.get("webhookSecret") or generate_webhook_secret(),
        "createdAt": now_ms(),
        "approvedAt": now_ms(),
        "notes": payload.get("notes") or "",
        "botInfo": bot_info,
        "startedUserCount": 0,
        "blacklistedUserCount": 0,
    }

    hook_url = build_bot_webhook_url(get_request_origin(request), bot_id)

    result = await telegram_raw(
        bot_token,
        "setWebhook",
        {
            "url": hook_url,
            "secret_token": bot["webhookSecret"],
        },
    )

    if not result.get("ok"):
        raise RuntimeError(f"set_webhook_failed: {json.dumps(result, ensure_ascii=False)}")

    await save_bot(bot)

    asyncio.create_task(register_bot_commands_safe(bot_token))

    logger.info(
        "perf onboarding bot_id=%s phase=create total_cost_ms=%s",
        bot_id,
        cost_ms(start_ts),
    )

    return {
        "tenant": tenant,
        "bot": bot,
        "webhook": {
            "url": hook_url,
            "secretToken": bot["webhookSecret"],
        },
        "telegram": result,
    }

async def create_bot_from_apply(request: Request, apply: dict) -> dict:
    return await create_bot_from_payload(
        request,
        {
            "tenantId": apply.get("tenantId"),
            "tenantName": apply.get("tenantName"),
            "botToken": apply.get("botToken"),
            "adminChatId": apply.get("applicantChatId"),
            "detailUrl": apply.get("detailUrl") or "",
            "status": "active",
            "creatorUsername": apply.get("creatorUsername") or apply.get("applicantUsername") or "",
            "creatorName": apply.get("creatorName") or apply.get("applicantDisplayName") or "",
            "welcomeButtons": apply.get("welcomeButtons") or [],
        },
    )


async def apply_bot_update(apply: dict) -> dict:
    bot_id = sanitize_tenant_id(apply.get("botId") or "")
    if not bot_id:
        raise ValueError("botId_required")

    bot = await load_bot(bot_id)
    if not bot:
        raise ValueError("bot_not_found")

    if int(bot.get("adminChatId", 0)) != int(apply.get("applicantChatId", 0)):
        raise ValueError("permission_denied")

    patch = apply.get("updatePatch") or {}
    allowed_keys = {
        "welcomeText",
        "welcomeButtons",
        "firstAckText",
        "detailUrl",
        "detailButtonText",
        "creatorUsername",
        "creatorName",
    }

    for key, value in patch.items():
        if key not in allowed_keys:
            raise ValueError(f"field_not_allowed:{key}")

        if key == "welcomeButtons":
            bot[key] = value if isinstance(value, list) else []
        else:
            bot[key] = str(value)

    bot["updatedAt"] = now_ms()
    await save_bot(bot)
    return {"bot": bot}


# ============================================================
# Platform bot flows
# ============================================================
async def try_handle_platform_blacklist_command(msg: dict) -> bool:
    platform_bot_token = get_platform_bot_token()
    chat_id = int((msg.get("chat") or {}).get("id") or 0)
    text = (msg.get("text") or "").strip()
    replied = msg.get("reply_to_message")

    # 主管理员、二级管理员都可以操作
    if not (is_primary_platform_admin(chat_id) or is_secondary_platform_admin(chat_id)):
        return False

    # 只处理精确命令
    if text not in {"拉黑", "解黑"}:
        return False

    # 必须是回复某条消息
    if not replied:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "请回复租户加入通知消息后再发送“拉黑”或“解黑”。",
        })
        return True

    target = await get_platform_notice_target(int(replied["message_id"]))
    if not target:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ 没有找到对应租户，请回复平台机器人发出的那条租户加入通知。",
        })
        return True

    tenant_id = sanitize_tenant_id(target.get("tenantId") or "")
    if not tenant_id:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ 租户标识无效。",
        })
        return True

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"⚠️ 租户不存在或已删除：{tenant_id}",
        })
        return True

    should_black = text == "拉黑"

    # 1. 写 Redis 黑名单
    await set_platform_tenant_blacklisted(tenant_id, should_black)

    # 2. 同步 tenant 本身字段，便于展示
    tenant["isBlacklisted"] = should_black
    tenant["updatedAt"] = now_ms()
    await save_tenant(tenant)
    
    # 3. 通知租户管理员（补上这段）
    tenant_admin_chat_id = int(tenant.get("adminChatId") or 0)
    if tenant_admin_chat_id:
        try:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": tenant_admin_chat_id,
                "text": (
                    "⛔ 你已被暂停使用！。"
                    if should_black else
                    "✅ 你已恢复使用！。"
                ),
            })
        except Exception:
            logger.exception("notify tenant blacklist state failed tenantId=%s", tenant_id)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已拉黑该租户" if should_black else "已解除拉黑",
    })

    tenant_admin_chat_id = int(tenant.get("adminChatId") or 0)

    # 3. 回平台管理员确认
    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            f"✅ 租户 {tenant_id} 已{'拉黑' if should_black else '解除拉黑'}。\n"
        ),
    })

    # 4. 通知租户管理员
    if tenant_admin_chat_id:
        try:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": tenant_admin_chat_id,
                "text": (
                    "⛔ 你已被暂停使用！。"
                    if should_black else
                    "✅ 你已恢复使用。"
                ),
            })
        except Exception:
            logger.exception("notify tenant blacklist state failed tenantId=%s", tenant_id)

    return True

async def handle_platform_message(msg: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    username = (msg.get("from") or {}).get("username") or ""
    first_name = (msg.get("from") or {}).get("first_name") or ""
    last_name = (msg.get("from") or {}).get("last_name") or ""
    name_text = " ".join([x for x in [first_name, last_name] if x]).strip()
    display_name = f"@{username}" if username else (name_text or f"UID:{chat_id}")

    is_platform_admin = (
        is_primary_platform_admin(chat_id)
        or is_secondary_platform_admin(chat_id)
    )
    if await try_handle_platform_blacklist_command(msg):
        return

    session = await load_apply_session(chat_id)
    admin_interrupt_text_actions = {
        "📊 数据概览",
        "🏢 所有租户",
        "🌐 全部群发",
        "📢 广告设置",
        "/start",
        "/cancel",
    }

    if (
        is_platform_admin
        and text in admin_interrupt_text_actions
        and is_busy_input_session(session)
    ):
        await clear_apply_session(chat_id)
        session = None



    if is_platform_admin and session and session.get("mode") == "platform_ad_config":
        step = session.get("step")

        if step == "ad_text_input":
            ad_text = text.strip()

            if not ad_text:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "广告文案不能为空，请重新输入。",
                })
                return

            # 这里限制字数，你自己定，我先给你 20 个字
            if len(ad_text) > 20:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"广告文案不能超过 20 个字，当前 {len(ad_text)} 个字，请重新输入。",
                })
                return

            session["adText"] = ad_text
            session["step"] = "ad_url_input"
            await save_apply_session(chat_id, session)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"广告文案已记录：{ad_text}\n\n"
                    "请继续发送广告链接。\n"
                ),
            })
            return

        if step == "ad_url_input":
            ad_url = text.strip()

            if not ad_url:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "广告链接不能为空，请重新输入。",
                })
                return

            if not re.match(r"^https?://", ad_url) and not re.match(r"^tg://", ad_url) and not re.match(r"^https://t\.me/", ad_url):
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "广告链接格式不正确，请发送完整链接，例如：https://t.me/kaiyunwind",
                })
                return

            ad_text = str(session.get("adText") or "").strip()
            if not ad_text:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "广告文案丢失，请重新进入广告设置。",
                })
                return

            items = await list_platform_ads()
            action = session.get("action") or "add"

            if action == "add":
                items.append({
                    "adId": generate_ad_id(),
                    "text": ad_text,
                    "url": ad_url,
                    "createdAt": now_ms(),
                    "updatedAt": now_ms(),
                })

            elif action == "edit":
                ad_id = str(session.get("adId") or "").strip()
                new_items = []

                for item in items:
                    if str(item.get("adId") or "").strip() == ad_id:
                        new_items.append({
                            **item,
                            "text": ad_text,
                            "url": ad_url,
                            "updatedAt": now_ms(),
                        })
                    else:
                        new_items.append(item)

                items = new_items

            await save_platform_ads(items)

            action = session.get("action") or "add"
            action_text = "新增成功" if action == "add" else "修改成功"

            await clear_apply_session(chat_id)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"✅ 广告{action_text}\n\n"
                    f"广告文案：{escape_html(ad_text)}\n"
                    f"广告链接：{escape_html(ad_url)}\n\n"
                    "显示效果：\n"
                    "广告：\n"
                    f'<a href="{html.escape(ad_url, quote=True)}">{escape_html(ad_text)}</a>'
                ),
                "parse_mode": "HTML",
                "link_preview_options": {
                    "is_disabled": True
                },
            })
            return

    current_tenant = await load_tenant_by_admin_chat_id(chat_id)
    if not is_platform_admin and current_tenant:
        tenant_id = sanitize_tenant_id(current_tenant.get("tenantId") or "")
        action_name = classify_platform_action(text)

        if action_name != "platform_plain_text":
            tenant_id = build_tenant_id_from_admin_chat_id(chat_id)

            limit_result = await get_bot_user_rate_limit_status(
                bot_id=tenant_id,
                user_id=chat_id,
                action=action_name,
            )
            if limit_result["blocked"]:
                if limit_result["message"]:
                    await tg(platform_bot_token, "sendMessage", {
                        "chat_id": chat_id,
                        "text": limit_result["message"],
                    })
                return

    if current_tenant:
        tenant_id = sanitize_tenant_id(current_tenant.get("tenantId") or "")
        if tenant_id and await is_platform_tenant_blacklisted(tenant_id):
            # 被拉黑租户，平台机器人直接忽略
            return

    # =========================================================
    # 首页 / 角色菜单
    # =========================================================
    if text.startswith("/start"):
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                "👋 欢迎使用双向机器人\n\n"
                + (
                    "你当前进入的是【平台管理员后台】"
                    if is_platform_admin
                    else "点击“添加机器人”开始"
                )
            ),
            "reply_markup": (
                build_platform_reply_keyboard_for_admin(chat_id)
                if is_platform_admin
                else build_platform_reply_keyboard_for_tenant()
            ),
        })
        return

    if is_secondary_platform_admin(chat_id) and text in {"🌐 全部群发", "📢 广告设置"}:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "❌ 你没有权限使用该功能。",
        })
        return

    if text.startswith("/cancel"):
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "✅ 已取消当前流程。",
        })
        return

    # =========================================================
    # 管理员功能区
    # =========================================================
    if is_platform_admin and session and session.get("mode") == "admin_tenant_broadcast":
        if session.get("step") == "broadcast_input":
            tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
            broadcast_text = text.strip()

            if not tenant_id or not broadcast_text:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "群发内容不能为空。",
                })
                return

            tenant = await load_tenant(tenant_id)
            if not tenant:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "租户不存在或已删除。",
                })
                return

            if await is_platform_tenant_blacklisted(tenant_id):
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户已被拉黑，禁止群发。",
                })
                return

            sender_bot = await pick_sender_bot_for_tenant(tenant_id)
            if not sender_bot:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户暂无可用机器人，无法群发。",
                })
                return

            users = await list_started_users_by_tenant_id(tenant_id)
            if not users:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户暂无启动用户，无法群发。",
                })
                return

            session["step"] = "broadcast_confirm"
            session["broadcastText"] = broadcast_text
            session["targetCount"] = len(users)
            session["senderBotId"] = str(sender_bot.get("botId") or "")
            session["senderBotUsername"] = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()
            await save_apply_session(chat_id, session)

            sender_show = (
                f"@{session['senderBotUsername']}"
                if session["senderBotUsername"] else session["senderBotId"]
            )

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"📣 即将群发给租户：{tenant.get('tenantName') or tenant_id}\n"
                    f"发送机器人：{sender_show}\n"
                    f"目标人数：{len(users)}\n\n"
                    f"群发内容：\n{broadcast_text}\n\n"
                    "请确认是否发送。"
                ),
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "✅ 确认", "callback_data": "admin_tenant_broadcast_confirm"},
                        {"text": "❌ 取消", "callback_data": "admin_tenant_broadcast_cancel"},
                    ]]
                },
            })
            return

    if is_platform_admin and session and session.get("mode") == "platform_global_broadcast":
        if session.get("step") == "broadcast_input":
            broadcast_text = text.strip()
            target_type = str(session.get("targetType") or "").strip()

            if not broadcast_text:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "群发内容不能为空。",
                })
                return

            target_label_map = {
                "tenants": "全部租户",
                "tenant_users": "全部租户的用户",
                "all_people": "所有人",
            }

            if target_type not in target_label_map:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "群发范围无效，请重新选择。",
                })
                return

            tenant_ids = await get_tenant_index()

            total_target = 0
            available_tenant_count = 0
            counted_platform_chat_ids = set()
            counted_tenant_user_pairs = set()

            for tenant_id in tenant_ids:
                tenant = await load_tenant(tenant_id)
                if not tenant:
                    continue

                if await is_platform_tenant_blacklisted(tenant_id):
                    continue

                admin_chat_id = int(tenant.get("adminChatId") or 0)
                users = await list_started_users_by_tenant_id(tenant_id)

                tenant_has_target = False

                if target_type == "tenants":
                    if admin_chat_id and admin_chat_id not in counted_platform_chat_ids:
                        counted_platform_chat_ids.add(admin_chat_id)
                        total_target += 1
                        tenant_has_target = True

                elif target_type == "tenant_users":
                    for u in users:
                        user_id = int(u.get("userId") or 0)
                        if not user_id:
                            continue

                        pair_key = (tenant_id, user_id)
                        if pair_key in counted_tenant_user_pairs:
                            continue

                        counted_tenant_user_pairs.add(pair_key)
                        total_target += 1
                        tenant_has_target = True

                elif target_type == "all_people":
                    if admin_chat_id and admin_chat_id not in counted_platform_chat_ids:
                        counted_platform_chat_ids.add(admin_chat_id)
                        total_target += 1
                        tenant_has_target = True

                    for u in users:
                        user_id = int(u.get("userId") or 0)
                        if not user_id:
                            continue

                        pair_key = (tenant_id, user_id)
                        if pair_key in counted_tenant_user_pairs:
                            continue

                        counted_tenant_user_pairs.add(pair_key)
                        total_target += 1
                        tenant_has_target = True

                if tenant_has_target:
                    available_tenant_count += 1

            if total_target <= 0:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "当前没有可群发的目标用户。",
                })
                return

            session["step"] = "broadcast_confirm"
            session["broadcastText"] = broadcast_text
            session["targetCount"] = total_target
            session["tenantCount"] = available_tenant_count
            await save_apply_session(chat_id, session)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "🌐 即将执行全部群发\n"
                    f"群发范围：{target_label_map[target_type]}\n"
                    f"目标租户数：{available_tenant_count}\n"
                    f"目标人数：{total_target}\n\n"
                    f"群发内容：\n{broadcast_text}\n\n"
                    "请确认是否发送。"
                ),
                "reply_markup": build_global_broadcast_confirm_buttons(),
            })
            return

    if is_platform_admin:
        if text == "📊 数据概览":
            dashboard_text = await build_platform_dashboard_text()

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": dashboard_text,
                "parse_mode": "HTML",
            })
            return

        if text == "🏢 所有租户":
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "🏢 所有租户\n\n请选择查看方式：",
                "reply_markup": build_admin_tenant_root_menu_buttons(),
            })
            return


        if text == "🌐 全部群发":
            await clear_apply_session(chat_id)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "请选择群发范围：",
                "reply_markup": build_global_broadcast_target_buttons(),
            })
            return

        if text == "📢 广告设置":
            items = await list_platform_ads()

            if not items:
                preview = "当前未设置广告。"
            else:
                lines = []
                for idx, item in enumerate(items[:10], start=1):
                    lines.append(
                        f"{idx}. {escape_html(item.get('text') or '')}\n"
                        f"   {escape_html(item.get('url') or '')}"
                    )
                preview = "\n\n".join(lines)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "📢 广告设置\n\n"
                    f"{preview}\n\n"
                    "请选择操作："
                ),
                "parse_mode": "HTML",
                "reply_markup": build_platform_ad_menu_buttons(),
                "link_preview_options": {
                    "is_disabled": True
                },
            })
            return

        if text.startswith("/users"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "用法：/users tenantId",
                })
                return

            tenant_id = sanitize_tenant_id(parts[1])
            if not tenant_id:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "tenantId 无效。",
                })
                return

            tenant = await load_tenant(tenant_id)
            if not tenant:
                await tg(platform_bot_token, "answerCallbackQuery", {
                    "callback_query_id": callback_id,
                    "text": "租户不存在",
                    "show_alert": True,
                })
                return

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "处理中...",
            })

            users = await list_started_users_by_tenant_id(tenant_id)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    (await format_tenant_summary_text(tenant))
                    + "\n\n"
                    + format_started_users_text(tenant, users)
                    + "\n\n"
                    + format_tenant_category_text(tenant)
                ),
                "parse_mode": "HTML",
            })
            return

        if text.startswith("/broadcast_all"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "用法：/broadcast_all 群发内容",
                })
                return

            broadcast_text = parts[1].strip()
            tenant_ids = await get_tenant_index()

            total_target = 0
            success = 0
            failed = 0

            for tenant_id in tenant_ids:
                tenant = await load_tenant(tenant_id)
                if not tenant:
                    continue

                if await is_platform_tenant_blacklisted(tenant_id):
                    continue

                users = await list_started_users_by_tenant_id(tenant_id)
                for u in users:
                    user_id = int(u["userId"])
                    total_target += 1

                    try:
                        await tg(tenant["botToken"], "sendMessage", {
                            "chat_id": user_id,
                            "text": broadcast_text,
                        })
                        success += 1
                    except Exception:
                        failed += 1

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "🌐 全部群发完成\n"
                    f"目标人数：{total_target}\n"
                    f"成功：{success}\n"
                    f"失败：{failed}"
                ),
            })
            return

        if text.startswith("/broadcast"):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "用法：/broadcast tenantId 群发内容",
                })
                return

            tenant_id = sanitize_tenant_id(parts[1])
            broadcast_text = parts[2].strip()

            if not tenant_id or not broadcast_text:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "参数不完整。用法：/broadcast tenantId 群发内容",
                })
                return

            tenant = await load_tenant(tenant_id)
            if not tenant:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "租户不存在。",
                })
                return

            if await is_platform_tenant_blacklisted(tenant_id):
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户已被拉黑，禁止操作。",
                })
                return

            users = await list_started_users_by_tenant_id(tenant_id)
            if not users:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户暂无启动用户，无法群发。",
                })
                return

            success = 0
            failed = 0

            for u in users:
                try:
                    await tg(tenant["botToken"], "sendMessage", {
                        "chat_id": int(u["userId"]),
                        "text": broadcast_text,
                    })
                    success += 1
                except Exception:
                    failed += 1

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "📣 单租户群发完成\n"
                    f"租户：{tenant_id}\n"
                    f"目标人数：{len(users)}\n"
                    f"成功：{success}\n"
                    f"失败：{failed}"
                ),
            })
            return

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                "管理员功能：\n"
                "1. 🏢 所有租户\n"
                "2. 👥 租户启动用户\n"
                "3. 📣 单租户群发\n"
                "4. 🌐 全部群发\n\n"
                "也可以直接使用命令：\n"
                "/users tenantId\n"
                "/broadcast tenantId 内容\n"
                "/broadcast_all 内容"
            ),
        })
        return

    # =========================================================
    # 租户功能区
    # =========================================================


    # 这些文本功能会“打断当前输入态”，直接切走
    interrupt_text_actions = {
        "📝 添加机器人",
        "📁 我的机器人",
        "🚫 查看黑名单",
        "📣 群发消息",
        "💬 帮助中心",
        "🇨🇳 切换中文包",
        "/apply",
        "/my",
        "/start",
        "/cancel",
    }

    if text in interrupt_text_actions:
        session = await interrupt_input_session_if_needed(
            chat_id,
            session,
            platform_bot_token=platform_bot_token,
            notify_chat_id=chat_id,
        )

    if text == "📁 我的机器人" or text.startswith("/my"):
        tenant = await load_tenant_by_admin_chat_id(chat_id)
        if not tenant:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "你暂未接入机器人。",
            })
            return

        bots = await list_bots_by_tenant_id(tenant["tenantId"])
        if not bots:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "你名下暂无机器人。",
            })
            return

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "Choose a bot from the list below:",
            "reply_markup": build_my_bots_entry_buttons(bots),
        })
        return

    if text == "📝 添加机器人" or text.startswith("/apply"):
        await save_apply_session(chat_id, {
            "mode": "create",
            "step": "bot_token",
            "applicantChatId": chat_id,
            "applicantUsername": username,
            "applicantDisplayName": display_name,
            "tenantName": username or name_text or f"user_{chat_id}",
            "tenantId": "",
            "botToken": "",
        })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "📝 开始添加\n\n请直接发送机器人 Bot Token。",
        })
        return

    if text == "🚫 查看黑名单":
        tenant = await load_tenant_by_admin_chat_id(chat_id)
        if not tenant:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "你暂未接入机器人。",
            })
            return

        bots = await list_bots_by_tenant_id(tenant["tenantId"])
        if not bots:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "你名下暂无机器人。",
            })
            return

        if len(bots) == 1:
            bot = bots[0]
            bot_id = sanitize_tenant_id(bot.get("botId") or "")
            users = await list_blacklisted_users(bot_id)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": format_blacklisted_users_text(bot, users),
                "parse_mode": "HTML",
            })
            return

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "请选择一个机器人查看黑名单：",
            "reply_markup": build_bot_pick_buttons(bots, "blacklist"),
        })
        return

    if text == "📣 群发消息":
        tenants = await list_tenants_by_admin_chat_id(chat_id)
        if not tenants:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "你暂未接入机器人。",
            })
            return

        if len(tenants) == 1:
            tenant = tenants[0]
            tenant_id = sanitize_tenant_id(tenant.get("tenantId") or "")

            await save_apply_session(chat_id, {
                "mode": "tenant_broadcast",
                "step": "broadcast_input",
                "tenantId": tenant_id,
                "tenantName": tenant.get("tenantName") or tenant_id,
                "botUsername": str(((tenant.get("botInfo") or {}).get("username") or "")).strip(),
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "你正在给 所有启动用户 群发。\n\n请直接发送群发内容。",
            })
            return

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "Please select robot：",
            "reply_markup": build_tenant_bot_pick_buttons(tenants, "broadcast"),
        })
        return

    if text == "💬 帮助中心":
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                "帮助中心\n\n"
                "一、如何创建机器人\n\n"
                "要创建机器人，您应遵循以下两个步骤：\n\n"
                "1. 打开 @BotFather 并创建一个新的机器人。\n\n"
                "2. 创建完成后，您会得到一个令牌（例如：12345:6789ABCDEF），"
                "只需将该令牌转发给我，或直接复制粘贴发送给我即可。\n\n"
                "3. 查看视频教程 >> <a href=\"https://t.me/SXX777bot/2\">查看</a>\n\n"
                "警告：\n"
                "请不要连接其他机器人服务，也不要使用已经接入过其他服务的机器人，"
                "否则可能会导致功能异常。\n\n"
                "二、如何拉黑 / 解黑用户\n\n"
                "1. 直接回复对方的启动信息，或对方发送的消息内容。\n\n"
                "2. 回复“拉黑”即可拉黑该用户，回复“解黑”即可解除拉黑。\n\n"
                "三、如何查看客户来源\n\n"
                "1. 当客户通过深链接启动您的机器人时，系统会自动提取并显示来源信息。\n\n"
                "2. 示例：\n"
                "https://t.me/你的机器人用户名?start=jisou\n\n"
                "如果客户通过这个链接启动您的机器人，来源将显示为：jisou\n\n"
                "3. 等号后面的来源参数可以自由设置。\n\n"
                "注意：\n"
                "来源参数不能使用中文，建议仅使用英文、数字、下划线（_）或短横线（-），这样更稳定。\n\n"
                "四、为什么机器人无法接入\n\n"
                "1. 请确认您发送的是 @BotFather 提供的完整 Bot Token。\n\n"
                "2. 请确认该机器人没有接入过其他机器人平台或第三方服务。\n\n"
                "3. 如果提示机器人已存在，说明该机器人已经接入过，无法重复接入。"
            ),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        return

    if text == "🇨🇳 切换中文包":
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "点击下方按钮切换 Telegram 中文语言包：",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "点击切换中文包", "url": "https://t.me/setlanguage/zhcncc"}
                ]]
            },
        })
        return

    if text.startswith("/modify"):
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "当前已不在底部菜单展示该功能，请按你的现有流程使用。",
        })
        return


    # =========================================================
    # create mode：只有在这里才监听 Bot Token
    # =========================================================
    if session and session.get("mode") == "create":
        if session.get("step") == "bot_token":
            bot_token = text.strip()
            me = await telegram_raw(bot_token, "getMe", {})
            if not me.get("ok"):
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": (
                        "❌ Bot Token 校验失败，请确认后重新发送。\n\n"
                        "提示：请发送形如 123456:ABC... 的完整 Token"
                    ),
                })
                return

            bot_info = me.get("result") or {}
            bot_username = str(bot_info.get("username") or "").strip()

            if not bot_username:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "❌ 机器人用户名获取失败，无法接入。",
                })
                return

            bot_id = build_bot_id_from_bot_username(bot_username)
            exists = await load_bot(bot_id)
            if exists and str(exists.get("status") or "active") != "deleted":
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"❌ 机器人 @{bot_username} 已经接入过了，无需重复申请。",
                })
                return

            tenant = await get_or_create_tenant_by_admin(
                chat_id,
                username=username,
                display_name=display_name,
            )

            tenant_name = username or name_text or f"user_{chat_id}"

            try:
                result = await create_bot_from_payload(
                    request,
                    {
                        "tenantId": tenant["tenantId"],
                        "tenantName": tenant.get("tenantName") or tenant_name,
                        "botToken": bot_token,
                        "botInfo": bot_info,
                        "adminChatId": chat_id,
                        "status": "active",
                        "creatorUsername": username,
                        "creatorName": display_name,
                        "welcomeButtons": [],
                    },
                )
            except Exception as err:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"❌ 接入失败：{str(err)}",
                })
                return

            await clear_apply_session(chat_id)
            session = None

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "✅ 接入成功\n\n"
                    f"机器人：@{bot_username}\n"
                ),
            })

            platform_admin_chat_id = get_platform_admin_chat_id()
            tenant_id = result["tenant"]["tenantId"]
            bot = result["bot"]

            asyncio.create_task(
                notify_new_bot_connected(
                    platform_bot_token=platform_bot_token,
                    platform_admin_chat_id=platform_admin_chat_id,
                    tenant_id=tenant_id,
                    tenant_name=tenant.get("tenantName") or tenant_name,
                    chat_id=chat_id,
                    username=username,
                    display_name=display_name,
                    bot=bot,
                )
            )

    # =========================================================
    # modify mode
    # =========================================================
    if session and session.get("mode") == "modify":
        if session.get("step") == "welcome_text_input":
            session["newValue"] = text
            session["step"] = "modify_confirm"
            await save_apply_session(chat_id, session)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"请确认修改申请：\n\n"
                    f"租户：{session['tenantId']}\n"
                    f"字段：{session['fieldLabel']}\n"
                    f"新值：\n{session['newValue']}"
                ),
                "reply_markup": build_modify_confirm_buttons(),
            })
            return

        if session.get("step") == "button_text_input":
            session["currentButtonText"] = text.strip()
            session["currentButtonReply"] = ""
            session["step"] = "button_reply_input"
            await save_apply_session(chat_id, session)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"请发送按钮“{session['currentButtonText']}”点击后要回复的内容。",
            })
            return

        if session.get("step") == "button_reply_input":
            btn_text = str(session.get("currentButtonText") or "").strip()
            btn_reply = text.strip()

            if not btn_text:
                session["step"] = "button_text_input"
                session["currentButtonReply"] = ""
                await save_apply_session(chat_id, session)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "按钮名称丢失了，请重新发送按钮名称。",
                })
                return

            drafts = session.get("buttonDrafts") or []
            drafts.append([{
                "text": btn_text,
                "reply": btn_reply,
            }])

            session["buttonDrafts"] = drafts
            session["newValue"] = drafts
            session["currentButtonText"] = ""
            session["currentButtonReply"] = ""
            session["step"] = "button_more_action"
            await save_apply_session(chat_id, session)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"已添加按钮：{btn_text}\n"
                    f"回复内容：{btn_reply}\n\n"
                    f"{format_button_preview(drafts)}\n\n"
                    "请选择下一步："
                ),
                "reply_markup": build_button_flow_action_buttons(),
            })
            return


    if session and session.get("mode") == "admin_tenant_broadcast":
        if session.get("step") == "broadcast_input":
            tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
            broadcast_text = text.strip()

            if not tenant_id or not broadcast_text:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "群发内容不能为空。",
                })
                return

            tenant = await load_tenant(tenant_id)
            if not tenant:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "租户不存在或已删除。",
                })
                return

            if await is_platform_tenant_blacklisted(tenant_id):
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户已被拉黑，禁止群发。",
                })
                return

            users = await list_started_users_by_tenant_id(tenant_id)
            if not users:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户暂无启动用户，无法群发。",
                })
                return

            success = 0
            failed = 0

            for u in users:
                user_id = int(u["userId"])
                try:
                    await tg(tenant["botToken"], "sendMessage", {
                        "chat_id": user_id,
                        "text": broadcast_text,
                    })
                    success += 1
                except Exception:
                    failed += 1

            await clear_apply_session(chat_id)

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "📣 群发完成\n"
                    f"租户：{tenant_id}\n"
                    f"目标人数：{len(users)}\n"
                    f"成功：{success}\n"
                    f"失败：{failed}"
                ),
            })
            return
    if session and session.get("mode") == "tenant_broadcast":
        if session.get("step") == "broadcast_input":
            tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
            bot_id = sanitize_tenant_id(session.get("botId") or "")
            broadcast_text = text.strip()

            if not tenant_id or not bot_id or not broadcast_text:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "群发内容不能为空。",
                })
                return

            tenant = await load_tenant(tenant_id)
            if not tenant:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "租户不存在或已删除。",
                })
                return

            if int(tenant.get("adminChatId", 0)) != int(chat_id):
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "你没有权限操作这个机器人。",
                })
                return

            if await is_platform_tenant_blacklisted(tenant_id):
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "该租户已被平台拉黑，禁止群发。",
                })
                return

            sender_bot = await load_bot(bot_id)
            if not sender_bot:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "机器人不存在或已删除，无法群发。",
                })
                return

            if str(sender_bot.get("tenantId") or "").strip() != tenant_id:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "机器人不属于当前租户，无法群发。",
                })
                return

            users = await list_started_users(bot_id)
            if not users:
                await clear_apply_session(chat_id)
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"发送机器人 @{session.get('botUsername') or bot_id} 暂无可群发用户。",
                })
                return

            session["step"] = "broadcast_confirm"
            session["broadcastText"] = broadcast_text
            session["targetCount"] = len(users)
            session["senderBotId"] = bot_id
            session["senderBotUsername"] = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()
            await save_apply_session(chat_id, session)

            sender_show = (
                f"@{session['senderBotUsername']}"
                if session["senderBotUsername"] else session["senderBotId"]
            )

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"📣 即将群发给机器人：{sender_show}\n"
                    f"目标人数：{len(users)}\n\n"
                    f"群发内容：\n{broadcast_text}\n\n"
                    "请确认是否发送。"
                ),
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "✅ 确认", "callback_data": "tenant_broadcast_confirm"},
                        {"text": "❌ 取消", "callback_data": "tenant_broadcast_cancel"},
                    ]]
                },
            })
            return


async def handle_platform_callback_query(callback_query: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    from_id = int((callback_query.get("from") or {}).get("id") or 0)
    data = str((callback_query.get("data") or "")).strip()
    message = callback_query.get("message") or {}

    # 二级管理员只拦指定平台功能
    if is_secondary_platform_admin(from_id):
        if (
            data.startswith("platform_ad_menu:")
            or data.startswith("platform_ad_pick:")
            or data.startswith("platform_global_broadcast")
            or data.startswith("platform_global_broadcast_target:")
            or data.startswith("admin_tenant_broadcast:")
            or data == "admin_tenant_broadcast_confirm"
            or data == "admin_tenant_broadcast_cancel"
        ):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "❌ 你没有权限执行此操作",
                "show_alert": True,
            })
            return

    # 先处理机器人侧 callback
    if (
        data.startswith("bot_manage:")
        or data.startswith("bot_select:")
        or data.startswith("bot_remove:")
        or data.startswith("bot_remove_confirm:")
        or data == "bot_remove_cancel"
        or data.startswith("button_flow:")
        or data.startswith("modify_submit:")
        or data == "bot_noop"
        or data == "bot_blacklist_back"
        or data.startswith("bot_blacklist_back:")
        or data.startswith("button_manage:")
        or data.startswith("button_delete:")
        or data == "tenant_broadcast_confirm"
        or data == "tenant_broadcast_cancel"
    ):
        await handle_bot_callback_query(callback_query, request)
        return

    # 再处理平台管理员 callback
    if not (is_primary_platform_admin(from_id) or is_secondary_platform_admin(from_id)):
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "无权限操作",
            "show_alert": True,
        })
        return


    if data == "admin_tenant_broadcast_cancel":
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已取消群发",
        })

        if message.get("chat", {}).get("id") and message.get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass
        return

    if data == "platform_global_broadcast_cancel":
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已取消全部群发",
        })

        if message.get("chat", {}).get("id") and message.get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass
        return

    if data == "platform_global_broadcast_confirm":
        session = await load_apply_session(from_id)
        if not session or session.get("mode") != "platform_global_broadcast" or session.get("step") != "broadcast_confirm":
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "全部群发会话已失效，请重新操作",
                "show_alert": True,
            })
            return

        broadcast_text = str(session.get("broadcastText") or "").strip()
        target_type = str(session.get("targetType") or "").strip()

        if not broadcast_text or target_type not in {"tenants", "tenant_users", "all_people"}:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "群发内容或范围无效，请重新操作",
                "show_alert": True,
            })
            return

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "开始全部群发",
        })

        tenant_ids = await get_tenant_index()

        total_target = 0
        success = 0
        failed = 0

        # 防止同一个 chat_id 被重复发送
        sent_platform_chat_ids = set()
        sent_tenant_user_pairs = set()   # (tenant_id, user_id)

        for tenant_id in tenant_ids:
            tenant = await load_tenant(tenant_id)
            if not tenant:
                continue

            if await is_platform_tenant_blacklisted(tenant_id):
                continue

            admin_chat_id = int(tenant.get("adminChatId") or 0)
            users = await list_started_users_by_tenant_id(tenant_id)

            sender_bot = await pick_sender_bot_for_tenant(tenant_id)
            tenant_bot_token = str(sender_bot.get("botToken") or "").strip() if sender_bot else ""

            if target_type == "tenants":
                if admin_chat_id and admin_chat_id not in sent_platform_chat_ids:
                    sent_platform_chat_ids.add(admin_chat_id)
                    total_target += 1
                    try:
                        await tg(platform_bot_token, "sendMessage", {
                            "chat_id": admin_chat_id,
                            "text": broadcast_text,
                        })
                        success += 1
                    except Exception:
                        failed += 1

            elif target_type == "tenant_users":
                if not tenant_bot_token:
                    continue

                for u in users:
                    user_id = int(u.get("userId") or 0)
                    if not user_id:
                        continue

                    pair_key = (tenant_id, user_id)
                    if pair_key in sent_tenant_user_pairs:
                        continue

                    sent_tenant_user_pairs.add(pair_key)
                    total_target += 1

                    try:
                        await tg(tenant_bot_token, "sendMessage", {
                            "chat_id": user_id,
                            "text": broadcast_text,
                        })
                        success += 1
                    except Exception:
                        failed += 1

            elif target_type == "all_people":
                if admin_chat_id and admin_chat_id not in sent_platform_chat_ids:
                    sent_platform_chat_ids.add(admin_chat_id)
                    total_target += 1
                    try:
                        await tg(platform_bot_token, "sendMessage", {
                            "chat_id": admin_chat_id,
                            "text": broadcast_text,
                        })
                        success += 1
                    except Exception:
                        failed += 1

                if not tenant_bot_token:
                    continue

                for u in users:
                    user_id = int(u.get("userId") or 0)
                    if not user_id:
                        continue

                    pair_key = (tenant_id, user_id)
                    if pair_key in sent_tenant_user_pairs:
                        continue

                    sent_tenant_user_pairs.add(pair_key)
                    total_target += 1

                    try:
                        await tg(tenant_bot_token, "sendMessage", {
                            "chat_id": user_id,
                            "text": broadcast_text,
                        })
                        success += 1
                    except Exception:
                        failed += 1

        await clear_apply_session(from_id)

        if message.get("chat", {}).get("id") and message.get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass

        target_label_map = {
            "tenants": "全部租户",
            "tenant_users": "全部租户的用户",
            "all_people": "所有人",
        }

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                "🌐 全部群发完成\n"
                f"范围：{target_label_map.get(target_type, target_type)}\n"
                f"目标人数：{total_target}\n"
                f"成功：{success}\n"
                f"失败：{failed}"
            ),
        })
        return

    if data == "admin_tenant_broadcast_confirm":
        session = await load_apply_session(from_id)
        if not session or session.get("mode") != "admin_tenant_broadcast" or session.get("step") != "broadcast_confirm":
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "群发会话已失效，请重新操作",
                "show_alert": True,
            })
            return

        tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
        broadcast_text = str(session.get("broadcastText") or "").strip()
        sender_bot_id = sanitize_tenant_id(session.get("senderBotId") or "")

        if not tenant_id or not broadcast_text or not sender_bot_id:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "群发内容无效，请重新操作",
                "show_alert": True,
            })
            return

        tenant = await load_tenant(tenant_id)
        if not tenant:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return

        if await is_platform_tenant_blacklisted(tenant_id):
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "该租户已被拉黑，禁止群发",
                "show_alert": True,
            })
            return

        sender_bot = await load_bot(sender_bot_id)
        if not sender_bot or str(sender_bot.get("status") or "active") != "active":
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "发送机器人不存在或不可用",
                "show_alert": True,
            })
            return

        if str(sender_bot.get("tenantId") or "") != tenant_id:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "发送机器人与租户不匹配",
                "show_alert": True,
            })
            return

        users = await list_started_users_by_tenant_id(tenant_id)
        if not users:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "该租户暂无启动用户",
                "show_alert": True,
            })
            return

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "开始群发",
        })

        success = 0
        failed = 0

        for u in users:
            user_id = int(u["userId"])
            try:
                await tg(sender_bot["botToken"], "sendMessage", {
                    "chat_id": user_id,
                    "text": broadcast_text,
                })
                success += 1
            except Exception:
                failed += 1

        await clear_apply_session(from_id)

        if message.get("chat", {}).get("id") and message.get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass

        sender_show = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()
        sender_show = f"@{sender_show}" if sender_show else str(sender_bot.get("botId") or "")

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                "📣 群发完成\n"
                f"租户：{tenant.get('tenantName') or tenant_id}\n"
                f"发送机器人：{sender_show}\n"
                f"目标人数：{len(users)}\n"
                f"成功：{success}\n"
                f"失败：{failed}"
            ),
        })
        return

    if data == "platform_global_broadcast_target:cancel":
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已取消",
        })

        if message.get("chat", {}).get("id") and message.get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass
        return

    if data.startswith("platform_global_broadcast_target:"):
        target_type = data.split(":", 1)[1].strip()

        if target_type not in {"tenants", "tenant_users", "all_people"}:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "无效的群发范围",
                "show_alert": True,
            })
            return

        await save_apply_session(from_id, {
            "mode": "platform_global_broadcast",
            "step": "broadcast_input",
            "targetType": target_type,
        })

        target_label_map = {
            "tenants": "全部租户",
            "tenant_users": "全部租户的用户",
            "all_people": "所有人",
        }

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": f"已选择：{target_label_map[target_type]}",
        })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": f"你正在给【{target_label_map[target_type]}】群发。\n\n请直接发送群发内容。",
        })
        return

    if data == "noop":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "暂无可操作内容",
        })
        return

    menu_match = re.match(r"^admin_tenant_menu:(traffic|category)$", data)
    if menu_match:
        menu_type = menu_match.group(1)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "请选择具体方式",
        })

        if not message.get("chat", {}).get("id") or not message.get("message_id"):
            return

        if menu_type == "traffic":
            await tg(platform_bot_token, "editMessageText", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "text": "🏢 所有租户\n\n请选择流量排序方式：",
                "reply_markup": build_admin_tenant_traffic_sort_buttons(),
            })
            return

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": "🏢 所有租户\n\n请选择租户分类：",
            "reply_markup": build_admin_tenant_category_buttons(),
        })
        return

    pick_match = re.match(r"^platform_ad_pick:(edit|delete):(.+)$", data)
    if pick_match:
        action = pick_match.group(1)
        ad_id = pick_match.group(2)

        ad_item = await get_platform_ad_by_id(ad_id)
        if not ad_item:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "广告不存在或已删除",
                "show_alert": True,
            })
            return

        if action == "edit":
            await save_apply_session(from_id, {
                "mode": "platform_ad_config",
                "step": "ad_text_input",
                "action": "edit",
                "adId": ad_id,
            })

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "请发送新的广告文案",
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": (
                    f"当前广告文案：{ad_item.get('text') or ''}\n"
                    f"当前广告链接：{ad_item.get('url') or ''}\n\n"
                    "请发送新的广告文案。"
                ),
            })
            return

        if action == "delete":
            items = await list_platform_ads()
            new_items = [x for x in items if str(x.get('adId') or '') != ad_id]

            await save_platform_ads(new_items)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "广告已删除",
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"✅ 已删除广告：{ad_item.get('text') or ad_id}",
            })
            return

    menu_match = re.match(r"^platform_ad_menu:(add|edit|delete)$", data)
    if menu_match:
        action = menu_match.group(1)

        if not (is_primary_platform_admin(from_id) or is_secondary_platform_admin(from_id)):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "无权限操作",
                "show_alert": True,
            })
            return

        if action == "add":
            await save_apply_session(from_id, {
                "mode": "platform_ad_config",
                "step": "ad_text_input",
                "action": "add",
            })

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "请发送广告文案",
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": (
                    "请输入广告文案。\n\n"
                    "要求：\n"
                    "1. 只显示一行\n"
                    "2. 不超过 20 个字\n"
                    "3. 例如：联系官方招商"
                ),
            })
            return

        if action == "edit":
            items = await list_platform_ads()
            if not items:
                await tg(platform_bot_token, "answerCallbackQuery", {
                    "callback_query_id": callback_query["id"],
                    "text": "当前没有广告可修改",
                    "show_alert": True,
                })
                return

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "请选择要修改的广告",
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请选择要修改的广告：",
                "reply_markup": build_platform_ad_pick_buttons(items, "edit"),
            })
            return

        if action == "delete":
            items = await list_platform_ads()
            if not items:
                await tg(platform_bot_token, "answerCallbackQuery", {
                    "callback_query_id": callback_query["id"],
                    "text": "当前没有广告可删除",
                    "show_alert": True,
                })
                return

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "请选择要删除的广告",
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请选择要删除的广告：",
                "reply_markup": build_platform_ad_pick_buttons(items, "delete"),
            })
            return

    broadcast_match = re.match(r"^admin_tenant_broadcast:(.+)$", data)
    if broadcast_match:
        tenant_id = sanitize_tenant_id(broadcast_match.group(1))
        tenant = await load_tenant(tenant_id)

        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return

        if await is_platform_tenant_blacklisted(tenant_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "该租户已被拉黑，禁止群发",
                "show_alert": True,
            })
            return

        await save_apply_session(from_id, {
            "mode": "admin_tenant_broadcast",
            "step": "broadcast_input",
            "tenantId": tenant_id,
            "tenantName": tenant.get("tenantName") or tenant_id,
            "botUsername": str(((tenant.get("botInfo") or {}).get("username") or "")).strip(),
        })

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "请直接发送群发内容",
        })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                f"你正在给租户 {tenant.get('tenantName') or tenant_id} "
                f"(@{((tenant.get('botInfo') or {}).get('username') or tenant_id)}) 群发。\n\n"
                "请直接发送要群发的内容。"
            ),
        })
        return

    black_match = re.match(r"^tenant_black_toggle:(black|unblack):(.+)$", data)
    if black_match:
        action = black_match.group(1)
        tenant_id = sanitize_tenant_id(black_match.group(2))

        tenant = await load_tenant(tenant_id)
        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return

        should_black = action == "black"

        # 1. 同步 Redis 黑名单
        await set_platform_tenant_blacklisted(tenant_id, should_black)

        # 2. 同步 tenant 展示字段
        tenant["isBlacklisted"] = should_black
        tenant["updatedAt"] = now_ms()
        await save_tenant(tenant)

        # 3. 通知租户管理员
        tenant_admin_chat_id = int(tenant.get("adminChatId") or 0)
        if tenant_admin_chat_id:
            try:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": tenant_admin_chat_id,
                    "text": (
                        "⛔ 你已被暂停使用。"
                        if should_black else
                        "✅ 你已恢复使用。"
                    ),
                })
            except Exception:
                logger.exception(
                    "notify tenant blacklist state failed tenantId=%s",
                    tenant_id,
                )

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已拉黑该租户" if should_black else "已解除拉黑",
        })

        # 4. 如果当前消息还能编辑，就把当前页面一起刷新
        if message.get("chat", {}).get("id") and message.get("message_id"):
            original_text = str(message.get("text") or "")

            if (
                "🟢 有新租户加入" in original_text
                or "🟢 <b>有新租户加入</b>" in original_text
                or "🟢 有新机器人接入" in original_text
                or "🟢 <b>有新机器人接入</b>" in original_text
            ):
                category = str(tenant.get("category") or "other")

                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "✅ 招商(本)" if category == "local" else "招商(本)",
                                    "callback_data": f"tenant_category:local:{tenant_id}"
                                },
                                {
                                    "text": "✅ 招商(外)" if category == "external" else "招商(外)",
                                    "callback_data": f"tenant_category:external:{tenant_id}"
                                },
                                {
                                    "text": "✅ 其他" if category == "other" else "其他",
                                    "callback_data": f"tenant_category:other:{tenant_id}"
                                },
                            ],
                            [
                                {
                                    "text": "✅ 已拉黑" if should_black else "拉黑",
                                    "callback_data": f"tenant_black_toggle:black:{tenant_id}"
                                },
                                {
                                    "text": "解黑" if should_black else "✅ 已解黑",
                                    "callback_data": f"tenant_black_toggle:unblack:{tenant_id}"
                                },
                            ]
                        ]
                    },
                })
                return

            users = await list_started_users_by_tenant_id(tenant_id)

            await tg(platform_bot_token, "editMessageText", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "text": (
                    await format_tenant_summary_text(tenant)
                    + "\n\n"
                    + format_started_users_text(tenant, users)
                    + "\n\n"
                    + format_tenant_category_text(tenant)
                ),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": build_tenant_detail_action_buttons(tenant_id, from_id),
            })

        return

    category_match = re.match(r"^tenant_category:(local|external|other):(.+)$", data)
    if category_match:
        category = category_match.group(1)
        tenant_id = sanitize_tenant_id(category_match.group(2))

        tenant = await load_tenant(tenant_id)
        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return

        category_label_map = {
            "local": "招商(本)",
            "external": "招商(外)",
            "other": "其他",
        }
        category_label = category_label_map.get(category, "其他")

        tenant["category"] = category
        tenant["updatedAt"] = now_ms()
        await save_tenant(tenant)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": f"已分类为：{category_label}",
        })

        await refresh_tenant_detail_message(
            platform_bot_token=platform_bot_token,
            message=message,
            tenant=tenant,
            from_id=from_id,
        )
        return

    back_match = re.match(r"^admin_tenant_back:(root|traffic|category)$", data)
    if back_match:
        back_to = back_match.group(1)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已返回",
        })

        if not message.get("chat", {}).get("id") or not message.get("message_id"):
            return

        if back_to == "root":
            await tg(platform_bot_token, "editMessageText", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "text": "🏢 所有租户\n\n请选择查看方式：",
                "reply_markup": build_admin_tenant_root_menu_buttons(),
            })
            return

        if back_to == "traffic":
            await tg(platform_bot_token, "editMessageText", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "text": "🏢 所有租户\n\n请选择流量排序方式：",
                "reply_markup": build_admin_tenant_traffic_sort_buttons(),
            })
            return

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": "🏢 所有租户\n\n请选择租户分类：",
            "reply_markup": build_admin_tenant_category_buttons(),
        })
        return

    sort_match = re.match(r"^admin_tenant_sort:(asc|desc)$", data)
    if sort_match:
        sort_type = sort_match.group(1)

        ids = await get_tenant_index()
        tenants = []

        for tenant_id in ids:
            tenant = await load_tenant(tenant_id)
            if not tenant:
                continue
            tenant["_started_count"] = int(tenant.get("startedUserCount") or 0)
            tenants.append(tenant)

        tenants.sort(
            key=lambda x: int(x.get("_started_count", 0)),
            reverse=(sort_type == "desc")
        )

        title = (
            "🏢 所有租户 · 按流量从高到低"
            if sort_type == "desc"
            else "🏢 所有租户 · 按流量从低到高"
        )

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已完成排序",
        })

        if not message.get("chat", {}).get("id") or not message.get("message_id"):
            return

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": format_simple_tenant_list_text(title, tenants),
            "parse_mode": "HTML",
            "reply_markup": build_admin_tenant_pick_buttons_with_back(
                tenants,
                "admin_tenant_back:traffic"
            ),
        })
        return

    filter_match = re.match(r"^admin_tenant_filter:category:(local|external|other|blacklisted)$", data)
    if filter_match:
        category = filter_match.group(1)

        ids = await get_tenant_index()
        tenants = []

        for tenant_id in ids:
            tenant = await load_tenant(tenant_id)
            if not tenant:
                continue

            if category == "blacklisted":
                if tenant.get("isBlacklisted"):
                    tenants.append(tenant)
            else:
                if tenant.get("isBlacklisted"):
                    continue

                tenant_category = str(tenant.get("category") or "other")
                if tenant_category not in {"local", "external", "other"}:
                    tenant_category = "other"

                if tenant_category == category:
                    tenants.append(tenant)

        category_label_map = {
            "local": "招商(本)",
            "external": "招商(外)",
            "other": "其他",
            "blacklisted": "已拉黑",
        }
        category_label = category_label_map.get(category, "其他")

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": f"已筛选：{category_label}",
        })

        if not message.get("chat", {}).get("id") or not message.get("message_id"):
            return

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": format_simple_tenant_list_text(
                f"🏢 所有租户 · 分类：{category_label}",
                tenants
            ),
            "parse_mode": "HTML",
            "reply_markup": build_admin_tenant_pick_buttons_with_back(
                tenants,
                "admin_tenant_back:category"
            ),
        })
        return



    tenant_view_match = re.match(r"^admin_tenant:view:(.+)$", data)
    if tenant_view_match:
        tenant_id = sanitize_tenant_id(tenant_view_match.group(1))
        tenant = await load_tenant(tenant_id)

        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "处理中...",
        })

        users = await list_started_users_by_tenant_id_for_admin(tenant_id)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                (await format_tenant_summary_text(tenant))
                + "\n\n"
                + format_started_users_text(tenant, users)
                + "\n\n"
                + format_tenant_category_text(tenant)
            ),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": build_tenant_detail_action_buttons(tenant_id, from_id),
        })
        return

    action = match.group(1)
    apply_id = match.group(2)
    apply = await load_apply(apply_id)

    if not apply:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "申请不存在或已过期",
            "show_alert": True,
        })
        return

    if apply.get("status") != "pending":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": f"该申请已处理：{apply.get('status')}",
            "show_alert": True,
        })
        return

    if action == "reject":
        apply["status"] = "rejected"
        apply["reviewedAt"] = now_ms()
        apply["reviewerChatId"] = from_id
        apply["reviewerAction"] = "reject"
        apply["rejectReason"] = "管理员拒绝"

        await save_apply(apply)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "已拒绝",
        })

        if message.get("chat", {}).get("id") and message.get("message_id"):
            await tg(platform_bot_token, "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": []},
            })
            await tg(platform_bot_token, "editMessageText", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "text": f"{build_apply_summary(apply)}\n\n❌ <b>已拒绝</b>",
                "parse_mode": "HTML",
            })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": apply["applicantChatId"],
            "text": (
                "❌ 很抱歉，你的修改申请未通过审核。"
                if apply.get("type") == "update"
                else "❌ 很抱歉，你的机器人接入申请未通过审核。"
            ),
        })
        return

    if action == "approve":
        try:
            if apply.get("type") == "update":
                await apply_bot_update(apply)
                apply["status"] = "approved"
                apply["reviewedAt"] = now_ms()
                apply["reviewerChatId"] = from_id
                apply["reviewerAction"] = "approve"
                await save_apply(apply)

                await tg(platform_bot_token, "answerCallbackQuery", {
                    "callback_query_id": callback_query["id"],
                    "text": "已同意修改",
                })

                if message.get("chat", {}).get("id") and message.get("message_id"):
                    await tg(platform_bot_token, "editMessageReplyMarkup", {
                        "chat_id": message["chat"]["id"],
                        "message_id": message["message_id"],
                        "reply_markup": {"inline_keyboard": []},
                    })
                    await tg(platform_bot_token, "editMessageText", {
                        "chat_id": message["chat"]["id"],
                        "message_id": message["message_id"],
                        "text": f"{build_apply_summary(apply)}\n\n✅ <b>修改已通过</b>",
                        "parse_mode": "HTML",
                    })

                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": apply["applicantChatId"],
                    "text": "✅ 你的修改申请已通过审核。\n新的配置已生效。",
                })
                return

            result = await create_bot_from_apply(request, apply)

            apply["status"] = "approved"
            apply["reviewedAt"] = now_ms()
            apply["reviewerChatId"] = from_id
            apply["reviewerAction"] = "approve"
            apply["approvedTenantId"] = result["tenant"]["tenantId"]
            await save_apply(apply)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "已同意并创建成功",
            })

            if message.get("chat", {}).get("id") and message.get("message_id"):
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
                await tg(platform_bot_token, "editMessageText", {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "text": (
                        f"{build_apply_summary(apply)}\n\n"
                        "✅ <b>已通过</b>\n"
                        f"🏢 tenantId：<code>{escape_html(result['tenant']['tenantId'])}</code>"
                    ),
                    "parse_mode": "HTML",
                })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": apply["applicantChatId"],
                "text": (
                    "✅ 你的机器人接入申请已通过审核。\n\n"
                    "机器人已完成接入，可以开始使用。\n"
                    "如需修改配置，请按现有流程进入对应机器人管理。"
                ),
            })

            await tg(apply["botToken"], "sendMessage", {
                "chat_id": apply["applicantChatId"],
                "text": "✅ 接入成功",
            })
            return

        except Exception as err:
            logger.exception("approve apply failed")
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "处理失败，查看日志",
                "show_alert": True,
            })

            if message.get("chat", {}).get("id"):
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": message["chat"]["id"],
                    "text": (
                        "❌ 处理申请失败\n"
                        f"申请ID：{apply.get('applyId')}\n"
                        f"错误：{str(err)}"
                    ),
                })

async def handle_bot_callback_query(callback_query: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    from_user = callback_query.get("from") or {}
    from_id = int(from_user.get("id") or 0)
    data = callback_query.get("data") or ""
    callback_id = callback_query["id"]

    username = from_user.get("username") or ""
    first_name = from_user.get("first_name") or ""
    last_name = from_user.get("last_name") or ""
    name_text = " ".join([x for x in [first_name, last_name] if x]).strip()
    display_name = f"@{username}" if username else (name_text or f"UID:{from_id}")

    if data == "bot_noop":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "暂无可操作机器人",
        })
        return

    if data == "bot_manage:back_to_list":
        tenant = await load_tenant_by_admin_chat_id(from_id)
        bots = []
        if tenant:
            bots = await list_bots_by_tenant_id(tenant["tenantId"])

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "返回机器人列表",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": "Choose a bot from the list below:",
            "reply_markup": build_my_bots_entry_buttons(bots),
        })
        return

    if data == "bot_blacklist_back":
        tenant = await load_tenant_by_admin_chat_id(from_id)
        bots = await list_bots_by_tenant_id(tenant["tenantId"]) if tenant else []

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "返回黑名单机器人列表",
        })
        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": "请选择一个机器人查看黑名单：",
            "reply_markup": build_bot_pick_buttons(bots, "blacklist"),
        })
        return

    m_blacklist_back = re.match(r"^bot_blacklist_back:(.+)$", data)
    if m_blacklist_back:
        bot_id = sanitize_tenant_id(m_blacklist_back.group(1))
        bot = await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "返回上一级",
        })
        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return

    bot = None
    bot_id = await extract_bot_id_from_callback_data(data)
    if bot_id:
        bot = await load_bot(bot_id)
        if bot:
            limit_result = await get_bot_user_rate_limit_status(
                bot_id=bot_id,
                user_id=from_id,
                action=f"callback:{data}",
            )
            if limit_result["blocked"]:
                if limit_result["message"]:
                    await tg(platform_bot_token, "answerCallbackQuery", {
                        "callback_query_id": callback_id,
                        "text": limit_result["message"],
                        "show_alert": True,
                    })
                return

    m_button_add = re.match(r"^button_manage:add:(.+)$", data)
    if m_button_add:
        bot_id = sanitize_tenant_id(m_button_add.group(1))
        bot = bot or await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        session = {
            "mode": "modify",
            "step": "button_text_input",
            "botId": bot_id,
            "tenantId": bot.get("tenantId") or "",
            "tenantName": bot.get("tenantName") or bot.get("tenantId") or "",
            "fieldKey": "welcomeButtons",
            "fieldLabel": "按钮",
            "applicantChatId": from_id,
            "applicantUsername": (from_user.get("username") or ""),
            "applicantDisplayName": display_name,
            "buttonDrafts": bot.get("welcomeButtons") or [],
            "currentButtonText": "",
            "currentButtonReply": "",
            "newValue": bot.get("welcomeButtons") or [],
        }
        await save_apply_session(from_id, session)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "开始添加按钮",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请发送按钮名称。",
        })
        return

    m_button_delete_menu = re.match(r"^button_manage:delete:(.+)$", data)
    if m_button_delete_menu:
        bot_id = sanitize_tenant_id(m_button_delete_menu.group(1))
        bot = await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        buttons = bot.get("welcomeButtons") or []
        flat_buttons = flatten_welcome_buttons(buttons)

        if not flat_buttons:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "当前没有可删除的按钮",
                "show_alert": True,
            })
            return

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请选择要删除的按钮",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请选择要删除的按钮：",
            "reply_markup": build_button_delete_pick_buttons(bot_id, buttons),
        })
        return

    m_button_delete = re.match(r"^button_delete:([^:]+):(\d+)$", data)
    if m_button_delete:
        bot_id = sanitize_tenant_id(m_button_delete.group(1))
        delete_index = int(m_button_delete.group(2))

        bot = await load_bot(bot_id)
        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        flat_buttons = flatten_welcome_buttons(bot.get("welcomeButtons") or [])
        if delete_index < 0 or delete_index >= len(flat_buttons):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "按钮不存在",
                "show_alert": True,
            })
            return

        deleted_name = str(flat_buttons[delete_index].get("text") or "").strip()
        del flat_buttons[delete_index]

        bot["welcomeButtons"] = rebuild_button_rows(flat_buttons)
        bot["updatedAt"] = now_ms()
        await save_bot(bot)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": f"已删除：{deleted_name}",
        })

        if flat_buttons:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"✅ 已删除按钮：{deleted_name}\n\n{format_button_preview(bot['welcomeButtons'])}",
                "reply_markup": build_button_delete_pick_buttons(bot_id, bot["welcomeButtons"]),
            })
        else:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"✅ 已删除按钮：{deleted_name}\n当前已无按钮。",
                "reply_markup": build_button_manage_menu_buttons(bot_id),
            })
        return

    m_button_menu = re.match(r"^button_manage:menu:(.+)$", data)
    if m_button_menu:
        bot_id = sanitize_tenant_id(m_button_menu.group(1))
        bot = await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "返回按钮菜单",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_button_manage_menu_buttons(bot_id),
        })
        return

    m_button_back = re.match(r"^button_manage:back:(.+)$", data)
    if m_button_back:
        bot_id = sanitize_tenant_id(m_button_back.group(1))
        bot = await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "返回上一级",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return

    # 第一层：点击机器人名字进入第二层操作菜单（不依赖 session）
    m_manage = re.match(r"^tenant_manage:(.+)$", data)
    if m_manage:
        tenant_id = sanitize_tenant_id(m_manage.group(1))
        tenant = await load_tenant(tenant_id)

        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(tenant.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        bot = await pick_default_bot_for_tenant(tenant_id)
        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "该租户下暂无可操作机器人",
                "show_alert": True,
            })
            return

        bot_id = str(bot.get("botId") or "").strip()
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请选择操作",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return

    m_manage = re.match(r"^bot_manage:(.+)$", data)
    if m_manage:
        bot_id = sanitize_tenant_id(m_manage.group(1))
        bot = bot or await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请选择操作",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return

    # 从这里开始才需要 session
    session = await load_apply_session(from_id)
    if (
        is_busy_input_session(session)
        and data not in {
            "admin_tenant_broadcast_confirm",
            "admin_tenant_broadcast_cancel",
            "platform_global_broadcast_confirm",
            "platform_global_broadcast_cancel",
            "platform_global_broadcast_target:cancel",
        }
        and (
            data.startswith("platform_ad_menu:")
            or data.startswith("platform_ad_pick:")
            or data.startswith("admin_tenant_broadcast:")
            or data.startswith("admin_tenant_menu:")
            or data.startswith("admin_tenant_sort:")
            or data.startswith("admin_tenant_filter:")
            or data.startswith("admin_tenant_back:")
            or data.startswith("admin_tenant:view:")
        )
    ):
        await clear_apply_session(from_id)
        session = None

    # 第二层：点击设置欢迎语 / 设置按钮
    m = re.match(r"^tenant_select:(welcome|buttons|blacklist|broadcast):(.+)$", data)
    if m:
        action = m.group(1)
        tenant_id = sanitize_tenant_id(m.group(2))

        tenant = await load_tenant(tenant_id)
        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(tenant.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        if not session:
            session = {
                "mode": "modify",
                "step": "",
                "applicantChatId": from_id,
                "applicantUsername": username,
                "applicantDisplayName": display_name,
                "tenantId": "",
                "tenantName": "",
                "botUsername": "",
                "fieldKey": "",
                "fieldLabel": "",
                "newValue": "",
                "buttonDrafts": [],
                "currentButtonText": "",
                "currentButtonReply": "",
            }

        bot_username = str(((tenant.get("botInfo") or {}).get("username") or "")).strip()

        session["tenantId"] = tenant_id
        session["tenantName"] = tenant.get("tenantName") or tenant_id
        session["botUsername"] = bot_username
        if action == "buttons":
            await clear_apply_session(from_id)

            bot = await pick_default_bot_for_tenant(tenant_id)
            if not bot:
                await tg(platform_bot_token, "answerCallbackQuery", {
                    "callback_query_id": callback_id,
                    "text": "该租户下暂无可操作机器人",
                    "show_alert": True,
                })
                return

            bot_id = str(bot.get("botId") or "").strip()
            bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
            show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请选择按钮操作",
            })
            await tg(platform_bot_token, "editMessageText", {
                "chat_id": callback_query["message"]["chat"]["id"],
                "message_id": callback_query["message"]["message_id"],
                "text": f"当前机器人：{show_name}",
                "reply_markup": build_button_manage_menu_buttons(bot_id),
            })
            return
        if action == "blacklist":
            started = time.perf_counter()

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "处理中...",
            })

            bots = await list_bots_by_tenant_id(tenant_id)
            all_users: List[dict] = []

            for bot in bots:
                bot_id = str(bot.get("botId") or "").strip()
                if not bot_id:
                    continue

                users = await list_blacklisted_users(bot_id)
                bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

                for u in users:
                    all_users.append({
                        **u,
                        "botId": bot_id,
                        "botUsername": bot_username,
                        "tenantId": tenant_id,
                    })

            all_users.sort(key=lambda x: int(x.get("userId") or 0))

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": format_tenant_blacklisted_users_text(tenant, all_users),
                "parse_mode": "HTML",
            })

            logger.info(
                "perf tenant_select:blacklist tenant_id=%s bots=%s users=%s cost_ms=%s",
                tenant_id,
                len(bots),
                len(all_users),
                cost_ms(started),
            )
            return

        if action == "broadcast":
            if not session:
                session = {}

            session["mode"] = "tenant_broadcast"
            session["step"] = "broadcast_input"
            session["tenantId"] = bot.get("tenantId") or ""
            session["tenantName"] = bot.get("tenantName") or bot.get("tenantId") or ""
            session["botId"] = bot_id
            session["botUsername"] = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "已选择机器人",
            })

            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"你正在给 @{session['botUsername'] or bot_id} 的启动用户群发。\n\n请直接发送群发内容。",
            })
            return

        if action == "welcome":
            session["fieldKey"] = "welcomeText"
            session["fieldLabel"] = "欢迎语"
            session["step"] = "welcome_text_input"
            session["newValue"] = ""
            session["buttonDrafts"] = []
            session["currentButtonText"] = ""
            session["currentButtonReply"] = ""
        else:
            session["fieldKey"] = "welcomeButtons"
            session["fieldLabel"] = "按钮"
            session["step"] = "button_text_input"
            session["newValue"] = []
            session["buttonDrafts"] = []
            session["currentButtonText"] = ""
            session["currentButtonReply"] = ""

        await save_apply_session(from_id, session)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已选择机器人",
        })

        if action == "welcome":
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"你正在修改 @{bot_username or tenant_id} 的欢迎语。\n\n请直接发送新的欢迎语内容。",
            })
        else:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"你正在修改 @{bot_username or tenant_id} 的按钮。\n\n请先发送按钮名称，例如：官网 / 联系客服 / 立即注册",
            })
        return

    m_remove = re.match(r"^tenant_remove:(.+)$", data)
    if m_remove:
        tenant_id = sanitize_tenant_id(m_remove.group(1))
        tenant = await load_tenant(tenant_id)

        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(tenant.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        bot_username = str(((tenant.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (tenant.get("tenantName") or tenant_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请确认",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"确认移除机器人 {show_name} 吗？",
            "reply_markup": build_remove_confirm_buttons(tenant_id),
        })
        return



    if data == "bot_remove_cancel":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "已取消移除操作。",
        })
        return

    m_select = re.match(r"^bot_select:(welcome|buttons|blacklist|broadcast):(.+)$", data)
    if m_select:
        action = m_select.group(1)
        bot_id = sanitize_tenant_id(m_select.group(2))
        bot = bot or await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        if action == "welcome":
            session = {
                "mode": "modify",
                "step": "welcome_text_input",
                "botId": bot_id,
                "tenantId": bot.get("tenantId") or "",
                "tenantName": bot.get("tenantName") or bot.get("tenantId") or "",
                "fieldKey": "welcomeText",
                "fieldLabel": "欢迎语",
                "applicantChatId": from_id,
                "applicantUsername": (callback_query.get("from") or {}).get("username") or "",
                "applicantDisplayName": (
                    ((callback_query.get("from") or {}).get("first_name") or "")
                    + (((callback_query.get("from") or {}).get("last_name") or "") and (" " + ((callback_query.get("from") or {}).get("last_name") or "")) or "")
                ).strip(),
                "newValue": str(bot.get("welcomeText") or ""),
            }
            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请发送新的欢迎语",
            })
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": (
                    "请发送新的欢迎语内容。\n\n"
                    "发送 skip 可使用默认欢迎语。"
                ),
            })
            return

        if action == "buttons":
            buttons = bot.get("welcomeButtons") or []

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "按钮管理",
            })
            await tg(platform_bot_token, "editMessageText", {
                "chat_id": callback_query["message"]["chat"]["id"],
                "message_id": callback_query["message"]["message_id"],
                "text": format_button_preview(buttons),
                "reply_markup": build_button_manage_menu_buttons(bot_id),
            })
            return

        if action == "blacklist":
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "处理中...",
            })

            users = await list_blacklisted_users(bot_id)

            await tg(platform_bot_token, "editMessageText", {
                "chat_id": callback_query["message"]["chat"]["id"],
                "message_id": callback_query["message"]["message_id"],
                "text": format_blacklisted_users_text(bot, users),
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "⬅️ 返回", "callback_data": f"bot_blacklist_back:{bot_id}"}
                    ]]
                },
            })
            return

        if action == "broadcast":
            session = {
                "mode": "tenant_broadcast",
                "step": "broadcast_input",
                "botId": bot_id,
                "tenantId": bot.get("tenantId") or "",
                "tenantName": bot.get("tenantName") or bot.get("tenantId") or "",
                "applicantChatId": from_id,
            }
            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请输入群发内容",
            })
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请发送要群发给该机器人用户的消息内容。",
            })
            return


    m_remove = re.match(r"^bot_remove:(.+)$", data)
    if m_remove:
        bot_id = sanitize_tenant_id(m_remove.group(1))
        bot = bot or await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请确认",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"确认移除机器人 {show_name} 吗？",
            "reply_markup": build_remove_confirm_buttons(bot_id),
        })
        return


    m_remove_confirm = re.match(r"^bot_remove_confirm:(.+)$", data)
    if m_remove_confirm:
        bot_id = sanitize_tenant_id(m_remove_confirm.group(1))
        bot = bot or await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        try:
            await telegram_raw(
                bot["botToken"],
                "deleteWebhook",
                {"drop_pending_updates": False}
            )
        except Exception:
            logger.exception("delete webhook failed botId=%s", bot_id)

        bot["status"] = "deleted"
        bot["deletedAt"] = now_ms()
        bot["updatedAt"] = now_ms()
        await save_bot(bot)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已移除",
        })

        tenant = await load_tenant(bot.get("tenantId") or "")
        bots = []
        if tenant:
            bots = await list_bots_by_tenant_id(tenant["tenantId"])

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": "请选择一个机器人：",
            "reply_markup": build_my_bots_entry_buttons(bots),
        })
        return


    if data == "bot_remove_cancel":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "已取消移除操作。",
        })
        return

    if not session:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "会话已过期，请重新开始",
            "show_alert": True,
        })
        return

    if data == "button_flow:add_more":
        session["step"] = "button_text_input"
        session["currentButtonText"] = ""
        session["currentButtonReply"] = ""
        await save_apply_session(from_id, session)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "继续添加",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请发送下一个按钮名称。",
        })
        return

    if data == "button_flow:finish":
        bot_id = sanitize_tenant_id(session.get("botId") or "")
        if not bot_id:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人无效",
                "show_alert": True,
            })
            return

        bot = bot or await load_bot(bot_id)
        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "无权限修改该机器人",
                "show_alert": True,
            })
            return

        buttons = session.get("buttonDrafts") or []
        bot["welcomeButtons"] = buttons if isinstance(buttons, list) else []
        bot["updatedAt"] = now_ms()
        await save_bot(bot)
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "按钮已保存",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "✅ 按钮已生效，请重新 /start 你的机器人即可。",
        })
        return

    if data == "button_flow:cancel":
        await clear_apply_session(from_id)
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "✅ 已取消当前按钮设置流程。",
        })
        return

    if data == "modify_submit:cancel":
        await clear_apply_session(from_id)
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "✅ 已取消当前修改流程。",
        })
        return

    if data == "modify_submit:retry":
        if session.get("fieldKey") == "welcomeText":
            session["step"] = "welcome_text_input"
            session["newValue"] = ""
            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请重新填写欢迎语",
            })
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请重新发送新的欢迎语内容。",
            })
            return

        if session.get("fieldKey") == "welcomeButtons":
            session["step"] = "button_text_input"
            session["buttonDrafts"] = []
            session["currentButtonText"] = ""
            session["currentButtonReply"] = ""
            session["newValue"] = []
            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请重新设置按钮",
            })
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请重新发送第一个按钮名称。",
            })
            return

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "当前内容不支持重试",
            "show_alert": True,
        })
        return

    if data == "tenant_broadcast_cancel":
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消群发",
        })

        if callback_query.get("message", {}).get("chat", {}).get("id") and callback_query.get("message", {}).get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": callback_query["message"]["chat"]["id"],
                    "message_id": callback_query["message"]["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass
        return


    if data == "tenant_broadcast_confirm":
        session = await load_apply_session(from_id)
        if not session or session.get("mode") != "tenant_broadcast" or session.get("step") != "broadcast_confirm":
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "群发会话已失效，请重新操作",
                "show_alert": True,
            })
            return

        tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
        sender_bot_id = sanitize_tenant_id(session.get("senderBotId") or session.get("botId") or "")
        broadcast_text = str(session.get("broadcastText") or "").strip()

        if not tenant_id or not sender_bot_id or not broadcast_text:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "群发参数无效，请重新操作",
                "show_alert": True,
            })
            return

        tenant = await load_tenant(tenant_id)
        if not tenant:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return

        if int(tenant.get("adminChatId", 0)) != int(from_id):
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return

        if await is_platform_tenant_blacklisted(tenant_id):
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "该租户已被平台拉黑，禁止群发",
                "show_alert": True,
            })
            return

        sender_bot = await load_bot(sender_bot_id)
        if not sender_bot or not str(sender_bot.get("botToken") or "").strip():
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "发送机器人不存在或不可用",
                "show_alert": True,
            })
            return

        if str(sender_bot.get("tenantId") or "").strip() != tenant_id:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不属于当前租户",
                "show_alert": True,
            })
            return

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "开始群发",
        })

        users = await list_started_users(sender_bot_id)
        success = 0
        failed = 0

        for u in users:
            user_id = int(u.get("userId") or 0)
            if not user_id:
                continue

            if await is_tenant_user_blacklisted(tenant_id, user_id):
                continue

            try:
                await tg(sender_bot["botToken"], "sendMessage", {
                    "chat_id": user_id,
                    "text": broadcast_text,
                })
                success += 1
            except Exception:
                logger.exception(
                    "tenant broadcast send failed tenant_id=%s sender_bot_id=%s user_id=%s",
                    tenant_id,
                    sender_bot_id,
                    user_id,
                )
                failed += 1

        await clear_apply_session(from_id)

        if callback_query.get("message", {}).get("chat", {}).get("id") and callback_query.get("message", {}).get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": callback_query["message"]["chat"]["id"],
                    "message_id": callback_query["message"]["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass

        sender_bot_username = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                "📣 群发完成\n"
                f"机器人：@{sender_bot_username or sender_bot_id}\n"
                f"目标人数：{len(users)}\n"
                f"成功：{success}\n"
                f"失败：{failed}"
            ),
        })
        return

    if data == "modify_submit:confirm":
        bot_id = sanitize_tenant_id(session.get("botId") or "")
        if not bot_id:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人无效",
                "show_alert": True,
            })
            return

        bot = bot or await load_bot(bot_id)
        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "无权限修改该机器人",
                "show_alert": True,
            })
            return

        field_key = str(session.get("fieldKey") or "").strip()
        new_value = session.get("newValue")

        if field_key == "welcomeText":
            bot["welcomeText"] = str(new_value or "").strip()
        elif field_key == "welcomeButtons":
            bot["welcomeButtons"] = new_value if isinstance(new_value, list) else []
        else:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "当前字段不支持直接保存",
                "show_alert": True,
            })
            return

        bot["updatedAt"] = now_ms()
        await save_bot(bot)
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "保存成功",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": f"✅ {session.get('fieldLabel') or '内容'} 已保存并立即生效。",
        })
        return

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "未知操作",
        "show_alert": True,
    })

async def extract_bot_id_from_callback_data(data: str) -> Optional[str]:
    if data in {"bot_noop", "bot_manage:back_to_list", "bot_blacklist_back"}:
        return ""
    data = str(data or "").strip()

    patterns = [
        r"^bot_select:[^:]+:(.+)$",
        r"^bot_manage:(.+)$",
        r"^bot_remove:(.+)$",
        r"^bot_remove_confirm:(.+)$",
        r"^button_manage:[^:]+:(.+)$",
        r"^button_delete:(.+):\d+$",
    ]

    for p in patterns:
        m = re.match(p, data)
        if m:
            return sanitize_tenant_id(m.group(1))

    return None




# ============================================================
# Tenant user/admin handlers
# ============================================================

def parse_start_payload(text: str = "") -> str:
    text = (text or "").strip()
    m = re.match(r"^/start(?:\s+(.+))?$", text)
    if not m:
        return ""
    return (m.group(1) or "").strip()


async def handle_user_message(msg: dict, bot: dict) -> None:
    user_id = (msg.get("from") or {}).get("id") or msg["chat"]["id"]
    username = (msg.get("from") or {}).get("username") or ""
    first_name = (msg.get("from") or {}).get("first_name") or ""
    last_name = (msg.get("from") or {}).get("last_name") or ""
    admin_chat_id = int(bot["adminChatId"])

    name_text = " ".join([x for x in [first_name, last_name] if x]).strip()
    display_name = f"@{username}" if username else (name_text or f"UID:{user_id}")
    user_link = build_user_link(int(user_id), username, display_name)

    text = (msg.get("text") or "").strip()
    start_payload = parse_start_payload(text)

    if int(user_id) != int(admin_chat_id):
        if await is_bot_user_blacklisted(bot["botId"], int(user_id)):
            return

    action_name = classify_message_action(text, bot)

    limit_result = await get_bot_user_rate_limit_status(
        bot_id=bot["botId"],
        user_id=int(user_id),
        action=action_name,
    )
    if limit_result["blocked"]:
        if limit_result["message"]:
            await reply_rate_limited_for_message(
                bot,
                int(msg["chat"]["id"]),
                limit_result["message"],
            )
        return

    if text.startswith("/start"):
        started_key = tenant_data_key(bot["tenantId"], "started", user_id)
        has_started = await redis_client.get(started_key)

        if start_payload:
            if start_payload:
                await redis_client.set(
                    tenant_data_key(bot["tenantId"], "source", user_id),
                    start_payload,
                )

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

        user_profile = {
            "userId": int(user_id),
            "username": username,
            "firstName": first_name,
            "lastName": last_name,
            "displayName": display_name,
            "source": start_payload or "direct",
            "startedAt": now_ms(),

            # 新增：记录是从哪个机器人启动的
            "botId": str(bot.get("botId") or "").strip(),
            "botUsername": bot_username,
            "tenantId": str(bot.get("tenantId") or "").strip(),
        }
        await save_started_user_profile(bot["botId"], user_profile)

        # 每次 /start 都发欢迎语和按钮
        ad_config = await load_platform_ad_config()

        await tg(bot["botToken"], "sendMessage", {
            "chat_id": user_id,
            "text": build_final_welcome_text(bot, ad_config),
            "parse_mode": "HTML",
            "link_preview_options": {
                "is_disabled": True
            },
            "reply_markup": build_bot_reply_keyboard(bot)
        })



        # 只有第一次 /start 才通知管理员
        if not has_started:
            source_text = start_payload or "direct"

            admin_text = (
                "🟢 <b>新用户启动</b>\n"
                "━━━━━━━━━━\n"
                f"👤 用户：{user_link}\n"
                f"🆔 UID：<code>{user_id}</code>\n"
                f"📍 来源：<code>{escape_html(source_text)}</code>"
            )

            sent = await tg(bot["botToken"], "sendMessage", {
                "chat_id": admin_chat_id,
                "text": admin_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })

            admin_message_id = ((sent or {}).get("result") or {}).get("message_id")
            if admin_message_id:
                await redis_client.set(
                    tenant_data_key(bot["tenantId"], "msg", admin_message_id),
                    str(user_id),
                    ex=MESSAGE_MAP_TTL_SECONDS,
                )

            await redis_client.set(started_key, "1")
            await check_bot_start_alert(bot, user_profile)

        return

    button_reply = find_bot_button_reply(bot, text)
    if button_reply:
        await tg(bot["botToken"], "sendMessage", {
            "chat_id": user_id,
            "text": button_reply,
        })
        return

    await refresh_lock_if_current(bot["tenantId"], admin_chat_id, int(user_id))

    admin_header = f"👤 用户：{user_link}\n🆔 UID：<code>{user_id}</code>"
    admin_message_id = None

    if msg.get("text") is not None:
        sent = await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": (
                f"{admin_header}\n\n"
                "💬 <b>内容：</b>\n"
                f"{escape_html(msg.get('text') or '')}"
            ),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        admin_message_id = ((sent or {}).get("result") or {}).get("message_id")
    else:
        caption_text = (
            f"{admin_header}\n\n"
            + (
                f"📝 <b>说明：</b>\n{escape_html(msg.get('caption') or '')}"
                if msg.get("caption")
                else "📎 <b>媒体消息</b>"
            )
        )
        sent = await tg(bot["botToken"], "copyMessage", {
            "chat_id": admin_chat_id,
            "from_chat_id": user_id,
            "message_id": msg["message_id"],
            "caption": caption_text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": build_profile_buttons(int(user_id), username, display_name)
            },
        })
        admin_message_id = ((sent or {}).get("result") or {}).get("message_id")

    if admin_message_id:
        await redis_client.set(
            tenant_data_key(bot["tenantId"], "msg", admin_message_id),
            str(user_id),
            ex=MESSAGE_MAP_TTL_SECONDS,
        )

    ack_key = tenant_data_key(bot["tenantId"], "ack", user_id)
    has_acked = await redis_client.get(ack_key)

    if not has_acked:
        await tg(bot["botToken"], "sendMessage", {
            "chat_id": user_id,
            "text": bot.get("firstAckText") or DEFAULT_FIRST_ACK_TEXT,
        })
        await redis_client.set(ack_key, "1", ex=FIRST_ACK_TTL_SECONDS)

async def try_handle_bot_user_blacklist_command(bot: dict, msg: dict) -> bool:
    bot_token = bot["botToken"]
    admin_chat_id = int(bot["adminChatId"])
    chat_id = int((msg.get("chat") or {}).get("id") or 0)
    text = (msg.get("text") or "").strip()
    replied = msg.get("reply_to_message")

    # 只有租户管理员自己的消息才处理
    if int(chat_id) != int(admin_chat_id):
        return False

    # 只处理拉黑 / 解黑
    if text not in {"拉黑", "解黑"}:
        return False

    # 必须回复某条用户消息
    if not replied:
        await tg(bot_token, "sendMessage", {
            "chat_id": admin_chat_id,
            "text": "请回复某个用户的启动消息或用户消息，然后发送“拉黑”或“解黑”。",
        })
        return True

    # 用管理员端那条转发消息的 message_id 找目标用户
    target_user_id = await redis_client.get(
        tenant_data_key(bot["tenantId"], "msg", replied["message_id"])
    )

    if not target_user_id:
        await tg(bot_token, "sendMessage", {
            "chat_id": admin_chat_id,
            "text": "⚠️ 没有找到对应用户，请回复机器人转发给你的那条用户消息。",
        })
        return True

    target_user_id = int(target_user_id)
    should_black = text == "拉黑"

    await set_bot_user_blacklisted(bot["botId"], target_user_id, should_black)

    await tg(bot_token, "sendMessage", {
        "chat_id": admin_chat_id,
        "text": f"✅ 用户 UID:{target_user_id} 已{'拉黑' if should_black else '解除拉黑'}。",
    })

    if should_black:
        try:
            await tg(bot_token, "sendMessage", {
                "chat_id": target_user_id,
                "text": "⛔ 你已被管理员暂停使用。",
            })
        except Exception:
            logger.exception(
                "notify blacklisted user failed botId=%s userId=%s",
                bot["botId"],
                target_user_id,
            )

    return True

def should_handle_as_admin_message(msg: dict) -> bool:
    text = str(msg.get("text") or "").strip()
    replied = msg.get("reply_to_message")

    # 只有这些场景才走管理员逻辑
    if replied:
        return True

    if text in {"拉黑", "解黑"}:
        return True

    return False

async def handle_admin_message(msg: dict, bot: dict) -> None:
    admin_chat_id = int(bot["adminChatId"])

    if await try_handle_bot_user_blacklist_command(bot, msg):
        return

    replied = msg.get("reply_to_message")
    if replied:
        target_user_id = await redis_client.get(
            tenant_data_key(bot["tenantId"], "msg", replied["message_id"])
        )
        if not target_user_id:
            await tg(bot["botToken"], "sendMessage", {
                "chat_id": admin_chat_id,
                "text": "⚠️ 没有找到对应用户，请回复机器人转发给你的那条消息。",
            })
            return

        await tg(bot["botToken"], "copyMessage", {
            "chat_id": int(target_user_id),
            "from_chat_id": admin_chat_id,
            "message_id": msg["message_id"],
        })

        await set_current_lock(bot["tenantId"], admin_chat_id, int(target_user_id))

        await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": f"✅ 已切换当前聊天用户为 UID:{target_user_id}（10分钟内有效）",
        })
        return

    locked_user_id = await get_current_lock(bot["tenantId"], admin_chat_id)
    if not locked_user_id:
        await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": "⚠️ 请先回复某条用户消息来锁定聊天对象，然后才能直接连续发送。",
        })
        return

    await tg(bot["botToken"], "copyMessage", {
        "chat_id": locked_user_id,
        "from_chat_id": admin_chat_id,
        "message_id": msg["message_id"],
    })


# ============================================================
# Internal API
# ============================================================

@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": APP_NAME,
    }


@app.post("/platform/webhook")
async def platform_webhook(request: Request):
    try:
        platform_bot_token = get_platform_bot_token()
        platform_admin_chat_id = get_platform_admin_chat_id()

        if not platform_bot_token:
            return json_response({"ok": False, "error": "platform_bot_token_missing"}, 500)
        if not platform_admin_chat_id:
            return json_response({"ok": False, "error": "platform_admin_chat_id_missing"}, 500)

        update = await request.json()

        if await is_duplicate_update("platform", update.get("update_id")):
            return {"ok": True, "ignored": "duplicate_update"}

        if update.get("callback_query"):
            await handle_platform_callback_query(update["callback_query"], request)
            return {"ok": True, "role": "platform_callback"}

        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return {"ok": True, "ignored": "no_message"}

        if (msg.get("chat") or {}).get("type") != "private":
            return {"ok": True, "ignored": "not_private"}

        await handle_platform_message(msg, request)
        return {"ok": True, "role": "platform_user"}

    except Exception as err:
        logger.exception("platform webhook error")
        return json_response({"ok": False, "error": str(err)}, 500)


@app.post("/webhook/{bot_id}")
async def bot_webhook(
    bot_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    try:
        bot = await load_bot(bot_id)
        if not bot:
            return json_response({"ok": False, "error": "bot_not_found"}, 404)

        if bot.get("status") != "active":
            return json_response({"ok": False, "error": "bot_inactive"}, 403)

        if bot.get("webhookSecret"):
            secret = x_telegram_bot_api_secret_token
            if secret != bot["webhookSecret"]:
                return json_response({"ok": False, "error": "unauthorized"}, 401)

        update = await request.json()

        if await is_duplicate_update(f"bot:{bot_id}", update.get("update_id")):
            return {"ok": True, "botId": bot_id, "ignored": "duplicate_update"}

        if update.get("callback_query"):
            callback_query = update["callback_query"]
            from_user = callback_query.get("from") or {}
            from_id = int(from_user.get("id") or 0)
            callback_id = callback_query.get("id")
            data = str(callback_query.get("data") or "").strip()

            limit_result = await get_bot_user_rate_limit_status(
                bot_id=bot_id,
                user_id=from_id,
                action=f"callback:{data}",
            )
            if limit_result["blocked"]:
                if limit_result["message"]:
                    await tg(bot["botToken"], "answerCallbackQuery", {
                        "callback_query_id": callback_id,
                        "text": limit_result["message"],
                        "show_alert": True,
                    })
                return {"ok": True, "botId": bot_id, "role": "bot_callback_rate_limited"}

            await tg(bot["botToken"], "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "已处理",
            })
            return {"ok": True, "botId": bot_id, "role": "bot_callback"}

        msg = update.get("message") or update.get("edited_message") or update.get("channel_post")
        if not msg:
            return {"ok": True, "botId": bot_id, "ignored": "no_message"}

        if (msg.get("chat") or {}).get("type") != "private":
            return {"ok": True, "botId": bot_id, "ignored": "not_private"}

        from_id = ((msg.get("from") or {}).get("id")) or msg["chat"]["id"]
        admin_chat_id = int(bot["adminChatId"])
        tenant_id = str(bot.get("tenantId") or "").strip()

        # 先拦被拉黑租户
        if tenant_id and await is_platform_tenant_blacklisted(tenant_id):
            if int(from_id) == int(admin_chat_id):
                await tg(bot["botToken"], "sendMessage", {
                    "chat_id": admin_chat_id,
                    "text": "⛔ 当前租户已被平台拉黑，已禁止与用户继续通信。",
                })
                return {"ok": True, "botId": bot_id, "role": "tenant_blacklisted_admin_blocked"}

            return {"ok": True, "botId": bot_id, "role": "tenant_blacklisted_ignored"}

        if int(from_id) == int(admin_chat_id):
            if should_handle_as_admin_message(msg):
                await handle_admin_message(msg, bot)
                return {"ok": True, "botId": bot_id, "role": "admin"}

            await handle_user_message(msg, bot)
            return {"ok": True, "botId": bot_id, "role": "admin_as_user"}

        await handle_user_message(msg, bot)
        return {"ok": True, "botId": bot_id, "role": "user"}

    except Exception as err:
        logger.exception("bot webhook error botId=%s", bot_id)
        return json_response({"ok": False, "error": str(err)}, 500)


@app.post("/internal/create-bot")
async def internal_create_bot(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    try:
        body = await request.json()
        result = await create_bot_from_payload(request, body)
        return {
            "ok": True,
            "tenantId": result["tenant"]["tenantId"],
            "tenant": result["tenant"],
            "bot": result["bot"],
            "webhook": result["webhook"],
            "telegram": result["telegram"],
        }
    except Exception as err:
        msg = str(err)
        code = 500
        if msg == "tenant_already_exists":
            code = 409
        elif msg.endswith("_required") or msg.startswith("bot_token_invalid"):
            code = 400
        return json_response({"ok": False, "error": msg}, code)


@app.get("/internal/get-tenant")
async def internal_get_tenant(
    request: Request,
    tenantId: str,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    tenant_id = sanitize_tenant_id(tenantId)
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    return {"ok": True, "tenant": tenant}


@app.get("/internal/list-tenants")
async def internal_list_tenants(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    ids = await get_tenant_index()
    tenants = []

    for tenant_id in ids:
        tenant = await load_tenant(tenant_id)
        if tenant:
            tenants.append({
                "tenantId": tenant.get("tenantId"),
                "tenantName": tenant.get("tenantName") or tenant.get("tenantId"),
                "status": tenant.get("status"),
                "adminChatId": tenant.get("adminChatId"),
                "detailUrl": tenant.get("detailUrl"),
                "createdAt": tenant.get("createdAt"),
                "approvedAt": tenant.get("approvedAt"),
                "updatedAt": tenant.get("updatedAt"),
            })

    return {"ok": True, "total": len(tenants), "tenants": tenants}


@app.get("/internal/list-applies")
async def internal_list_applies(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    ids = await get_apply_index(100)
    applies = []

    for apply_id in ids:
        apply = await load_apply(apply_id)
        if apply:
            applies.append({
                "applyId": apply.get("applyId"),
                "type": apply.get("type") or "create",
                "status": apply.get("status"),
                "applicantChatId": apply.get("applicantChatId"),
                "applicantDisplayName": apply.get("applicantDisplayName"),
                "tenantName": apply.get("tenantName"),
                "tenantId": apply.get("tenantId"),
                "detailUrl": apply.get("detailUrl"),
                "updatePatch": apply.get("updatePatch"),
                "createdAt": apply.get("createdAt"),
                "reviewedAt": apply.get("reviewedAt"),
                "approvedTenantId": apply.get("approvedTenantId"),
            })

    return {"ok": True, "total": len(applies), "applies": applies}


@app.post("/internal/disable-tenant")
async def internal_disable_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    tenant["status"] = "disabled"
    tenant["disabledAt"] = now_ms()
    await save_tenant(tenant)

    return {"ok": True, "tenantId": tenant_id, "status": tenant["status"]}


@app.post("/internal/enable-tenant")
async def internal_enable_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    tenant["status"] = "active"
    tenant["enabledAt"] = now_ms()
    await save_tenant(tenant)

    return {"ok": True, "tenantId": tenant_id, "status": tenant["status"]}


@app.post("/internal/delete-tenant")
async def internal_delete_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    await delete_tenant(tenant_id)
    return {"ok": True, "tenantId": tenant_id, "deleted": True}


@app.post("/internal/setup-webhook")
async def internal_setup_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    hook_url = build_bot_webhook_url(get_request_origin(request), bot_id)
    result = await telegram_raw(tenant["botToken"], "setWebhook", {
        "url": hook_url,
        "secret_token": tenant["webhookSecret"],
    })

    return {
        "ok": True,
        "tenantId": tenant_id,
        "webhook": {
            "url": hook_url,
            "secretToken": tenant["webhookSecret"],
        },
        "telegram": result,
    }


@app.post("/internal/setup-platform-webhook")
async def internal_setup_platform_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    platform_bot_token = get_platform_bot_token()
    if not platform_bot_token:
        return json_response({"ok": False, "error": "platform_bot_token_missing"}, 500)

    url = f"{get_request_origin(request)}/platform/webhook"
    result = await telegram_raw(platform_bot_token, "setWebhook", {"url": url})

    return {
        "ok": True,
        "webhook": {"url": url},
        "telegram": result,
    }


# ============================================================
# Entrypoint
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

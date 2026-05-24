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
from app.services.reply_service import (
    reply_rate_limited_for_callback,
    reply_rate_limited_for_message,
)
from app.services.stat_service import (
    incr_bot_stat,
    incr_tenant_stat,
)
from app.services.lock_service import (
    acquire_short_lock,
    release_short_lock,
    set_current_lock,
    get_current_lock,
    refresh_lock_if_current,
)
from app.core.keys import (
    tenant_started_users_key,
    bot_stat_lock_key,
    tenant_stat_lock_key,
    bot_started_users_key,
    bot_start_alert_window_key,
    bot_start_alert_cooldown_key,
    tenant_latest_bot_id_key,
    tenant_key,
    bot_key,
    bot_index_key,
    tenant_bots_key,
    tenant_all_bots_key,
    tenant_index_key,
    tenant_data_key,
)
from app.utils.helpers import (
    cost_ms,
    now_ms,
    json_response,
    safe_json_dumps,
    sanitize_tenant_id,
    format_date_ymd,
    is_primary_platform_admin,
    is_secondary_platform_admin,
    build_bot_id_from_bot_username,
    build_tenant_id_from_admin_chat_id,
    escape_html,
    mask_bot_token,
    is_skip_text,
    get_today_ymd,
    is_same_ymd_ts_ms,
    build_user_link,
)
from app.core.lifespan import lifespan
from app.services.user_service import (
    find_bot_button_reply,
    bot_user_profile_key,
    check_bot_start_alert,
)
from app.services.blacklist_service import (
    bot_user_black_key,
    bot_user_blacklist_set_key,
    platform_tenant_black_key,
    is_tenant_user_blacklisted,
    list_blacklisted_users_by_tenant_id,
    list_blacklisted_users,
    format_blacklisted_users_text,
    format_tenant_blacklisted_users_text,
)
from app.services.notice_service import (
    platform_tenant_notice_map_key,
    map_platform_notice_message,
    get_platform_notice_target,
)
from app.services.apply_service import (
    generate_apply_id,
    apply_key,
    apply_index_key,
    apply_session_key,
    load_apply,
    save_apply,
    get_apply_index,
    load_apply_session,
    save_apply_session,
    clear_apply_session,
    create_bot_from_apply,
    apply_bot_update,
)
from app.services.ad_service import (
    platform_ad_config_key,
    load_platform_ad_config,
    save_platform_ad_config,
    delete_platform_ad_config,
    generate_ad_id,
    normalize_ad_item,
)
from app.services.rate_limit_service import (
    normalize_rate_action,
    bot_user_rate_action_key,
    bot_user_rate_mute_notice_key,
    bot_user_rate_burst_key,
    bot_user_rate_mute_key,
    is_duplicate_update,
    get_bot_user_rate_limit_status,
)
from app.services.bot_service import (
    load_bot_by_bot_username,
    list_started_users,
    load_bot,
    save_bot,
    get_bot_index,
    add_bot_index,
    remove_bot_index,
    pick_default_bot_for_tenant,
    pick_sender_bot_for_tenant,
    save_started_user_profile,
    set_bot_user_blacklisted,
    is_bot_user_blacklisted,
)
from app.services.tenant_service import (
    load_tenant,
    save_tenant,
    load_tenant_by_admin_chat_id,
    get_tenant_index,
    add_tenant_index,
    remove_tenant_index,
    list_bots_by_tenant_id,
    list_all_bots_by_tenant_id,
    list_started_users_by_tenant_id,
    list_started_users_by_tenant_id_for_admin,
    recompute_tenant_today_started_user_count,
    set_platform_tenant_blacklisted,
    is_platform_tenant_blacklisted,
)
from app.routes.health import router as health_router
from app.routes.platform import router as platform_router
from app.routes.webhook import router as webhook_router
from app.routes.internal import router as internal_router
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

# redis_client 已由 app.storage.redis_compat 提供
# telegram_http_client 已迁移到 app.telegram.api




app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.include_router(health_router)
app.include_router(platform_router)
app.include_router(webhook_router)
app.include_router(internal_router)




from app.core.request_helpers import (
    build_bot_webhook_url,
    generate_webhook_secret,
    get_platform_admin_chat_id,
    get_platform_bot_token,
    get_request_origin,
    require_internal_api_key,
)

from app.services.message_classify_service import (classify_message_action, classify_platform_action, is_plain_user_text_message)

from app.services.platform_ad_service import (get_platform_ad_by_id, list_platform_ads, save_platform_ads)

from app.services.tenant_query_service import (list_tenants_by_admin_chat_id, redis_get_json, redis_set_json)

from app.services.input_session_service import (interrupt_input_session_if_needed, is_busy_input_session, is_input_session)

from app.services.message_parse_service import (extract_bot_id_from_callback_data, parse_start_payload, should_handle_as_admin_message)

from app.services.platform_notice_view_service import (is_new_tenant_notice_text, notify_new_bot_connected, refresh_tenant_detail_message, refresh_tenant_latest_bot_id)

from app.services.bot_onboarding_service import (create_bot_from_payload, get_or_create_tenant_by_admin)

from app.services.platform_dashboard_view_service import (build_platform_dashboard_text, format_simple_tenant_list_text)

from app.services.bot_user_blacklist_command_service import try_handle_bot_user_blacklist_command

from app.services.admin_message_service import handle_admin_message

from app.services.user_message_service import handle_user_message

from app.services.bot_button_callback_service import try_handle_bot_button_callback

from app.services.bot_remove_callback_service import try_handle_bot_remove_callback

# ============================================================
# Helpers
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

    if await try_handle_bot_button_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_user=from_user,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        display_name=display_name,
        bot=bot,
    ):
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


    if await try_handle_bot_remove_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
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





# ============================================================
# Tenant user/admin handlers
# ============================================================








# ============================================================
# Internal API
# ============================================================





# route moved to app.routes.internal
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


# route moved to app.routes.internal
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


# route moved to app.routes.internal
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

import os
import re
import html
import logging
import asyncio
from typing import Optional

from fastapi import FastAPI, Header, Request
from app.utils.helpers import (
    now_ms,
    json_response,
    sanitize_tenant_id,
    is_primary_platform_admin,
    is_secondary_platform_admin,
    build_bot_id_from_bot_username,
    build_tenant_id_from_admin_chat_id,
    escape_html,
)
from app.core.lifespan import lifespan
from app.services.blacklist_service import (
    list_blacklisted_users,
    format_blacklisted_users_text,
)
from app.services.notice_service import (
    get_platform_notice_target,
)
from app.services.apply_service import (
    load_apply,
    get_apply_index,
    load_apply_session,
    save_apply_session,
    clear_apply_session,
)
from app.services.ad_service import (
    generate_ad_id,
)
from app.services.rate_limit_service import (
    get_bot_user_rate_limit_status,
)
from app.services.bot_service import (
    list_started_users,
    load_bot,
    pick_sender_bot_for_tenant,
)
from app.services.tenant_service import (
    load_tenant,
    save_tenant,
    load_tenant_by_admin_chat_id,
    get_tenant_index,
    list_bots_by_tenant_id,
    list_started_users_by_tenant_id,
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
)
from app.telegram.formatters import (
    format_button_preview,
    format_tenant_summary_text,
    format_started_users_text,
    format_tenant_category_text,
)
from app.telegram.keyboards import (
    build_bot_pick_buttons,
    build_button_flow_action_buttons,
    build_global_broadcast_confirm_buttons,
    build_global_broadcast_target_buttons,
    build_modify_confirm_buttons,
    build_my_bots_entry_buttons,
    build_platform_reply_keyboard_for_admin,
    build_platform_ad_menu_buttons,
    build_platform_reply_keyboard_for_tenant,
    build_admin_tenant_root_menu_buttons,
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
    get_platform_admin_chat_id,
    get_platform_bot_token,
    get_request_origin,
    require_internal_api_key,
)







from app.services.bot_onboarding_service import (create_bot_from_payload, get_or_create_tenant_by_admin)











from app.services.bot_callback_context_service import build_bot_callback_context
from app.services.bot_callback_dispatch_service import dispatch_bot_callback
from app.services.platform_callback_dispatch_service import dispatch_platform_callback
from app.services.platform_admin_tenant_broadcast_input_service import try_handle_platform_admin_tenant_broadcast_input
from app.services.platform_global_broadcast_input_service import try_handle_platform_global_broadcast_input
from app.services.platform_ad_settings_message_service import try_handle_platform_ad_settings_message
from app.services.platform_dashboard_message_service import try_handle_platform_dashboard_message
from app.services.platform_tenant_list_menu_message_service import try_handle_platform_tenant_list_menu_message
from app.services.platform_global_broadcast_menu_message_service import try_handle_platform_global_broadcast_menu_message
from app.services.platform_users_command_service import try_handle_platform_users_command
from app.services.platform_broadcast_all_command_service import try_handle_platform_broadcast_all_command
from app.services.platform_broadcast_command_service import try_handle_platform_broadcast_command
from app.services.platform_admin_help_message_service import try_handle_platform_admin_help_message
from app.services.tenant_my_bots_message_service import try_handle_tenant_my_bots_message
from app.services.tenant_apply_start_message_service import try_handle_tenant_apply_start_message
from app.services.tenant_blacklist_view_message_service import try_handle_tenant_blacklist_view_message
from app.services.tenant_broadcast_start_message_service import try_handle_tenant_broadcast_start_message
from app.services.tenant_help_message_service import try_handle_tenant_help_message
from app.services.tenant_language_pack_message_service import try_handle_tenant_language_pack_message
from app.services.tenant_modify_deprecated_message_service import try_handle_tenant_modify_deprecated_message
from app.services.tenant_broadcast_input_message_service import try_handle_tenant_broadcast_input_message
from app.services.tenant_modify_input_message_service import try_handle_tenant_modify_input_message
from app.services.tenant_create_bot_token_message_service import try_handle_tenant_create_bot_token_message
from app.services.platform_admin_tenant_broadcast_legacy_input_service import try_handle_platform_admin_tenant_broadcast_legacy_input
from app.services.platform_ad_config_input_service import try_handle_platform_ad_config_input
from app.services.platform_start_message_service import try_handle_platform_start_message
from app.services.platform_cancel_message_service import try_handle_platform_cancel_message
from app.services.platform_secondary_admin_restricted_message_service import try_handle_platform_secondary_admin_restricted_message
from app.services.platform_admin_interrupt_session_service import interrupt_platform_admin_input_session_if_needed

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
    session = await interrupt_platform_admin_input_session_if_needed(
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
        session=session,
    )



    if is_platform_admin and await try_handle_platform_ad_config_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
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
    if await try_handle_platform_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
    ):
        return

    if await try_handle_platform_secondary_admin_restricted_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    if await try_handle_platform_cancel_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    # =========================================================
    # 管理员功能区
    # =========================================================
    if is_platform_admin and await try_handle_platform_admin_tenant_broadcast_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return

    if is_platform_admin and await try_handle_platform_global_broadcast_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return

    if is_platform_admin:
        if await try_handle_platform_dashboard_message(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return

        if await try_handle_platform_tenant_list_menu_message(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return


        if await try_handle_platform_global_broadcast_menu_message(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return

        if await try_handle_platform_ad_settings_message(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return

        if await try_handle_platform_users_command(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return

        if await try_handle_platform_broadcast_all_command(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return

        if await try_handle_platform_broadcast_command(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
            text=text,
        ):
            return

        await try_handle_platform_admin_help_message(
            platform_bot_token=platform_bot_token,
            chat_id=chat_id,
        )
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

    if await try_handle_tenant_my_bots_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    if await try_handle_tenant_apply_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        display_name=display_name,
        name_text=name_text,
    ):
        return

    if await try_handle_tenant_blacklist_view_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    if await try_handle_tenant_broadcast_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    if await try_handle_tenant_help_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    if await try_handle_tenant_language_pack_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return

    if await try_handle_tenant_modify_deprecated_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return


    # =========================================================
    # create mode：只有在这里才监听 Bot Token
    # =========================================================
    if await try_handle_tenant_create_bot_token_message(
        request=request,
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        display_name=display_name,
        name_text=name_text,
        session=session,
    ):
        return

    # =========================================================
    # modify mode
    # =========================================================
    if await try_handle_tenant_modify_input_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return


    if await try_handle_platform_admin_tenant_broadcast_legacy_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return
    if await try_handle_tenant_broadcast_input_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return


async def handle_platform_callback_query(callback_query: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    from_id = int((callback_query.get("from") or {}).get("id") or 0)
    data = str((callback_query.get("data") or "")).strip()
    message = callback_query.get("message") or {}

    if await dispatch_platform_callback(
        request=request,
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return


async def handle_bot_callback_query(callback_query: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    callback_context = build_bot_callback_context(callback_query=callback_query)
    from_user = callback_context["from_user"]
    from_id = callback_context["from_id"]
    data = callback_context["data"]
    callback_id = callback_context["callback_id"]
    username = callback_context["username"]
    display_name = callback_context["display_name"]

    if await dispatch_bot_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_user=from_user,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        username=username,
        display_name=display_name,
    ):
        return



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

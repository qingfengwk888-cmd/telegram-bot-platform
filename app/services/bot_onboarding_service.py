import asyncio
import json
import logging
import time

from fastapi import Request

from app.config import DEFAULT_FIRST_ACK_TEXT, DEFAULT_WELCOME_TEXT
from app.core.request_helpers import build_bot_webhook_url, generate_webhook_secret, get_request_origin
from app.services.bot_service import load_bot_by_bot_username, save_bot
from app.services.tenant_service import load_tenant, save_tenant
from app.telegram.api import register_bot_commands_safe, telegram_raw
from app.utils.helpers import (
    build_bot_id_from_bot_username,
    build_tenant_id_from_admin_chat_id,
    cost_ms,
    now_ms,
)

logger = logging.getLogger(__name__)


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

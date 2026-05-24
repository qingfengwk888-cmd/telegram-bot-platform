from typing import Optional

from fastapi import Header, Request

from app.core.request_helpers import (
    build_bot_webhook_url,
    get_platform_bot_token,
    get_request_origin,
    require_internal_api_key,
)
from app.core.responses import json_response
from app.services.bot_service import (
    load_bot,
    load_bot_by_bot_username,
    pick_default_bot_for_tenant,
)
from app.services.tenant_service import load_tenant
from app.telegram.api import telegram_raw
from app.utils.helpers import sanitize_tenant_id


async def internal_setup_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()

    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    bot_id = sanitize_tenant_id(body.get("botId") or "")
    bot_username = str(body.get("botUsername") or "").strip().lstrip("@")

    if not tenant_id and not bot_id and not bot_username:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = None
    if tenant_id:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    bot = None
    if bot_id:
        bot = await load_bot(bot_id)
    elif bot_username:
        bot = await load_bot_by_bot_username(bot_username)
    elif tenant_id:
        bot = await pick_default_bot_for_tenant(tenant_id)

    if not bot:
        return json_response({"ok": False, "error": "bot_not_found"}, 404)

    if tenant_id and sanitize_tenant_id(bot.get("tenantId") or "") != tenant_id:
        return json_response({"ok": False, "error": "bot_tenant_mismatch"}, 400)

    bot_id = sanitize_tenant_id(bot.get("botId") or "")
    if not bot_id:
        return json_response({"ok": False, "error": "botId_required"}, 400)

    bot_token = str(bot.get("botToken") or "").strip()
    if not bot_token:
        return json_response({"ok": False, "error": "botToken_required"}, 400)

    webhook_secret = str(bot.get("webhookSecret") or "").strip()
    if not webhook_secret:
        return json_response({"ok": False, "error": "webhookSecret_required"}, 400)

    hook_url = build_bot_webhook_url(get_request_origin(request), bot_id)
    result = await telegram_raw(bot_token, "setWebhook", {
        "url": hook_url,
        "secret_token": webhook_secret,
    })

    return {
        "ok": True,
        "tenantId": sanitize_tenant_id(bot.get("tenantId") or tenant_id),
        "botId": bot_id,
        "webhook": {
            "url": hook_url,
            "secretToken": webhook_secret,
        },
        "telegram": result,
    }


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
        "webhook": {
            "url": url,
        },
        "telegram": result,
    }

from typing import Optional

from fastapi import APIRouter, Header, Request

from app.core.logger import logger
from app.telegram.api import tg
from app.utils.helpers import json_response
from app.services.bot_service import load_bot
from app.services.rate_limit_service import is_duplicate_update, get_bot_user_rate_limit_status
from app.services.tenant_service import is_platform_tenant_blacklisted
from app.services.message_parse_service import should_handle_as_admin_message
from app.services.admin_message_service import handle_admin_message
from app.services.user_message_service import handle_user_message

router = APIRouter()


@router.post("/webhook/{bot_id}")
async def bot_webhook(
    bot_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    """
    子机器人 webhook 路由。

    当前阶段：
    - 路由入口已经迁出 legacy_app
    - 业务处理函数仍临时调用 legacy_app
    """
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

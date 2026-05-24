import logging
import re
from typing import Optional

from app.services.bot_service import load_bot, save_bot
from app.services.tenant_service import list_bots_by_tenant_id, load_tenant
from app.telegram.api import telegram_raw, tg
from app.telegram.keyboards import build_my_bots_entry_buttons, build_remove_confirm_buttons
from app.utils.helpers import now_ms, sanitize_tenant_id

logger = logging.getLogger(__name__)


async def try_handle_bot_remove_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    bot: Optional[dict] = None,
) -> bool:
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
            return True

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return True

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
        return True


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
            return True

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return True

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
        return True

    return False

import re
from typing import Optional

from app.services.apply_service import save_apply_session
from app.services.blacklist_service import list_blacklisted_users, format_blacklisted_users_text
from app.services.bot_service import load_bot
from app.telegram.api import tg
from app.telegram.formatters import format_button_preview
from app.telegram.keyboards import build_button_manage_menu_buttons
from app.utils.helpers import sanitize_tenant_id


async def try_handle_bot_select_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    bot: Optional[dict] = None,
) -> bool:
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
            return True

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return True

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
            return True

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
            return True

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
            return True

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
            return True

    return False

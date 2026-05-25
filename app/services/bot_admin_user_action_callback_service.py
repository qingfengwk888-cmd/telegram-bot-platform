import re

from app.services.bot_service import is_bot_user_blacklisted, set_bot_user_blacklisted
from app.services.lock_service import set_current_lock
from app.telegram.api import tg
from app.telegram.keyboards import build_admin_user_action_buttons


async def try_handle_bot_admin_user_action_callback(
    *,
    bot_id: str,
    bot: dict,
    callback_query: dict,
) -> bool:
    data = str(callback_query.get("data") or "").strip()
    callback_id = callback_query.get("id")
    message = callback_query.get("message") or {}
    from_user = callback_query.get("from") or {}
    from_id = int(from_user.get("id") or 0)
    admin_chat_id = int(bot["adminChatId"])

    if not data.startswith("admin_user_"):
        return False

    if int(from_id) != int(admin_chat_id):
        await tg(bot["botToken"], "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "无权限操作",
            "show_alert": True,
        })
        return True

    reply_match = re.match(r"^admin_user_reply:(\d+)$", data)
    if reply_match:
        user_id = int(reply_match.group(1))

        await set_current_lock(
            bot["tenantId"],
            admin_chat_id,
            {
                "type": "user_chat",
                "user_id": user_id,
            },
            ttl_seconds=600,
        )

        await tg(bot["botToken"], "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已切换回复对象",
            "show_alert": False,
        })

        await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": f"✅ 已切换当前聊天用户为 UID:{user_id}（10分钟内有效）\n现在直接发送消息即可回复该用户。",
        })
        return True

    black_match = re.match(r"^admin_user_black:(black|unblack):(\d+)$", data)
    if black_match:
        action = black_match.group(1)
        user_id = int(black_match.group(2))
        should_black = action == "black"

        await set_bot_user_blacklisted(bot_id, user_id, should_black)

        is_blacklisted = await is_bot_user_blacklisted(bot_id, user_id)
        text = f"用户 UID:{user_id} 已{'拉黑' if should_black else '解除拉黑'}"

        await tg(bot["botToken"], "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": text,
            "show_alert": False,
        })

        if message.get("chat") and message.get("message_id"):
            await tg(bot["botToken"], "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": build_admin_user_action_buttons(user_id, is_blacklisted),
            })

        if should_black:
            try:
                await tg(bot["botToken"], "sendMessage", {
                    "chat_id": user_id,
                    "text": "⛔ 你已被管理员暂停使用。",
                })
            except Exception:
                pass

        return True

    return False

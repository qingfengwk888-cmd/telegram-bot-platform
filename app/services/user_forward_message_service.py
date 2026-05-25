from app.config import DEFAULT_FIRST_ACK_TEXT, FIRST_ACK_TTL_SECONDS, MESSAGE_MAP_TTL_SECONDS
from app.services.bot_service import is_bot_user_blacklisted
from app.core.keys import tenant_data_key
from app.storage.redis_compat import redis_client
from app.telegram.api import tg
from app.telegram.formatters import escape_html
from app.telegram.keyboards import build_admin_user_action_buttons


async def forward_user_message_to_admin_and_ack(
    *,
    msg: dict,
    bot: dict,
    user_id: int,
    username: str,
    display_name: str,
    user_link: str,
    admin_chat_id: int,
) -> None:
    admin_header = f"👤 用户：{user_link}\n🆔 UID：<code>{user_id}</code>"
    is_blacklisted = await is_bot_user_blacklisted(bot["botId"], int(user_id))
    admin_action_buttons = build_admin_user_action_buttons(int(user_id), is_blacklisted)
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
            "reply_markup": admin_action_buttons,
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
            "reply_markup": admin_action_buttons,
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

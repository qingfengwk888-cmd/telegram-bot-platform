from app.config import DEFAULT_FIRST_ACK_TEXT, FIRST_ACK_TTL_SECONDS, MESSAGE_MAP_TTL_SECONDS
from app.core.keys import tenant_data_key
from app.services.bot_service import is_bot_user_blacklisted
from app.services.user_service import find_bot_button_reply
from app.services.user_start_message_service import try_handle_user_start_message
from app.telegram.formatters import escape_html
from app.telegram.keyboards import build_profile_buttons
from app.utils.helpers import build_user_link
from app.services.lock_service import refresh_lock_if_current
from app.services.message_classify_service import classify_message_action
from app.services.message_parse_service import parse_start_payload
from app.services.rate_limit_service import get_bot_user_rate_limit_status
from app.services.reply_service import reply_rate_limited_for_message
from app.storage.redis_compat import redis_client
from app.telegram.api import tg


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

    if await try_handle_user_start_message(
        msg=msg,
        bot=bot,
        user_id=int(user_id),
        username=username,
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
        user_link=user_link,
        text=text,
        start_payload=start_payload,
        admin_chat_id=admin_chat_id,
    ):
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

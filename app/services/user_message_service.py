from app.services.bot_service import is_bot_user_blacklisted
from app.services.user_service import find_bot_button_reply
from app.services.user_start_message_service import try_handle_user_start_message
from app.services.user_forward_message_service import forward_user_message_to_admin_and_ack
from app.utils.helpers import build_user_link
from app.services.lock_service import refresh_lock_if_current
from app.services.message_classify_service import classify_message_action
from app.services.message_parse_service import parse_start_payload
from app.services.rate_limit_service import get_bot_user_rate_limit_status
from app.services.reply_service import reply_rate_limited_for_message
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

    await forward_user_message_to_admin_and_ack(
        msg=msg,
        bot=bot,
        user_id=int(user_id),
        username=username,
        display_name=display_name,
        user_link=user_link,
        admin_chat_id=admin_chat_id,
    )

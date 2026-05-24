from app.services.bot_service import is_bot_user_blacklisted
from app.services.message_classify_service import classify_message_action
from app.services.rate_limit_service import get_bot_user_rate_limit_status
from app.services.reply_service import reply_rate_limited_for_message


async def should_skip_user_message_before_dispatch(
    *,
    msg: dict,
    bot: dict,
    user_id: int,
    admin_chat_id: int,
    text: str,
) -> bool:
    if int(user_id) != int(admin_chat_id):
        if await is_bot_user_blacklisted(bot["botId"], int(user_id)):
            return True

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
        return True

    return False

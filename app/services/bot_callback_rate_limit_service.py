async def resolve_bot_for_callback_and_check_rate_limit(
    *,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
):
    from app.telegram.api import tg
    from app.services.message_parse_service import extract_bot_id_from_callback_data
    from app.services.bot_service import load_bot
    from app.services.rate_limit_service import get_bot_user_rate_limit_status

    bot = None
    bot_id = await extract_bot_id_from_callback_data(data)

    if bot_id:
        bot = await load_bot(bot_id)
        if bot:
            limit_result = await get_bot_user_rate_limit_status(
                bot_id=bot_id,
                user_id=from_id,
                action=f"callback:{data}",
            )
            if limit_result["blocked"]:
                if limit_result["message"]:
                    await tg(platform_bot_token, "answerCallbackQuery", {
                        "callback_query_id": callback_id,
                        "text": limit_result["message"],
                        "show_alert": True,
                    })
                return True, bot_id, bot

    return False, bot_id, bot

async def resolve_bot_for_callback_and_check_rate_limit(
    *,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
):
    from app import legacy_app as legacy

    bot = None
    bot_id = await legacy.extract_bot_id_from_callback_data(data)

    if bot_id:
        bot = await legacy.load_bot(bot_id)
        if bot:
            limit_result = await legacy.get_bot_user_rate_limit_status(
                bot_id=bot_id,
                user_id=from_id,
                action=f"callback:{data}",
            )
            if limit_result["blocked"]:
                if limit_result["message"]:
                    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
                        "callback_query_id": callback_id,
                        "text": limit_result["message"],
                        "show_alert": True,
                    })
                return True, bot_id, bot

    return False, bot_id, bot

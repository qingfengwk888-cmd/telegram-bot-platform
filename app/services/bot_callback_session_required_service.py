async def try_handle_missing_bot_callback_session(
    *,
    platform_bot_token: str,
    callback_id: str,
    session: dict | None,
) -> bool:
    from app import legacy_app as legacy

    if session:
        return False

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "会话已过期，请重新开始",
        "show_alert": True,
    })
    return True

async def try_handle_missing_bot_callback_session(
    *,
    platform_bot_token: str,
    callback_id: str,
    session: dict | None,
) -> bool:
    from app.telegram.api import tg

    if session:
        return False

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "会话已过期，请重新开始",
        "show_alert": True,
    })
    return True

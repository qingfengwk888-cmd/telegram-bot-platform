async def answer_unknown_bot_callback_action(
    *,
    platform_bot_token: str,
    callback_id: str,
) -> None:
    from app.telegram.api import tg

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "未知操作",
        "show_alert": True,
    })

async def try_handle_platform_noop_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
) -> bool:
    from app.telegram.api import tg

    if data != "noop":
        return False

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "暂无可操作内容",
    })
    return True

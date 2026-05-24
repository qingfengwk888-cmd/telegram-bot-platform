async def try_handle_bot_noop_callback(
    *,
    platform_bot_token: str,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    if data != "bot_noop":
        return False

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "暂无可操作机器人",
    })
    return True

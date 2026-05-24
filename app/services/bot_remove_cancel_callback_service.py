async def try_handle_bot_remove_cancel_callback(
    *,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    if data != "bot_remove_cancel":
        return False

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "已取消",
    })
    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": "已取消移除操作。",
    })
    return True

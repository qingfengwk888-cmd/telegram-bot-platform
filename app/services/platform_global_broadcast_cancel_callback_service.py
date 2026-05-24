async def try_handle_platform_global_broadcast_cancel_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.services.apply_service import clear_apply_session

    if data != "platform_global_broadcast_cancel":
        return False

    await clear_apply_session(from_id)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已取消全部群发",
    })

    if message.get("chat", {}).get("id") and message.get("message_id"):
        try:
            await tg(platform_bot_token, "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": []},
            })
        except Exception:
            pass

    return True

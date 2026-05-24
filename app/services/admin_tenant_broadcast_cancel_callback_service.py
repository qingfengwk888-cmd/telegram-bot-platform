async def try_handle_admin_tenant_broadcast_cancel_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy

    if data != "admin_tenant_broadcast_cancel":
        return False

    await legacy.clear_apply_session(from_id)

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已取消群发",
    })

    if message.get("chat", {}).get("id") and message.get("message_id"):
        try:
            await legacy.tg(platform_bot_token, "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": []},
            })
        except Exception:
            pass

    return True

async def try_handle_bot_blacklist_back_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    if data != "bot_blacklist_back":
        return False

    tenant = await legacy.load_tenant_by_admin_chat_id(from_id)
    bots = await legacy.list_bots_by_tenant_id(tenant["tenantId"]) if tenant else []

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "返回黑名单机器人列表",
    })
    await legacy.tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": "请选择一个机器人查看黑名单：",
        "reply_markup": legacy.build_bot_pick_buttons(bots, "blacklist"),
    })
    return True

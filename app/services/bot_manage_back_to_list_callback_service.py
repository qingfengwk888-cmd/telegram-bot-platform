async def try_handle_bot_manage_back_to_list_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app.telegram.api import tg
    from app.services.tenant_service import load_tenant_by_admin_chat_id, list_bots_by_tenant_id
    from app.telegram.keyboards import build_my_bots_entry_buttons

    if data != "bot_manage:back_to_list":
        return False

    tenant = await load_tenant_by_admin_chat_id(from_id)
    bots = []
    if tenant:
        bots = await list_bots_by_tenant_id(tenant["tenantId"])

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "返回机器人列表",
    })

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": "Choose a bot from the list below:",
        "reply_markup": build_my_bots_entry_buttons(bots),
    })
    return True

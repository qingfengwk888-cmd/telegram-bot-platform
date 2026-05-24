async def try_route_platform_bot_callback(
    *,
    callback_query: dict,
    request,
    data: str,
) -> bool:
    from app import legacy_app as legacy

    if (
        data.startswith("bot_manage:")
        or data.startswith("bot_select:")
        or data.startswith("bot_remove:")
        or data.startswith("bot_remove_confirm:")
        or data == "bot_remove_cancel"
        or data.startswith("button_flow:")
        or data.startswith("modify_submit:")
        or data == "bot_noop"
        or data == "bot_blacklist_back"
        or data.startswith("bot_blacklist_back:")
        or data.startswith("button_manage:")
        or data.startswith("button_delete:")
        or data == "tenant_broadcast_confirm"
        or data == "tenant_broadcast_cancel"
    ):
        await legacy.handle_bot_callback_query(callback_query, request)
        return True

    return False

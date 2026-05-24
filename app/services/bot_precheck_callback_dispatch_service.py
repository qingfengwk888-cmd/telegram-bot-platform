async def dispatch_bot_precheck_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app.services.bot_noop_callback_service import try_handle_bot_noop_callback
    from app.services.bot_manage_back_to_list_callback_service import try_handle_bot_manage_back_to_list_callback
    from app.services.bot_blacklist_back_callback_service import try_handle_bot_blacklist_back_callback
    from app.services.bot_blacklist_detail_back_callback_service import try_handle_bot_blacklist_detail_back_callback

    if await try_handle_bot_noop_callback(
        platform_bot_token=platform_bot_token,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_bot_manage_back_to_list_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_bot_blacklist_back_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_bot_blacklist_detail_back_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
        callback_id=callback_id,
    ):
        return True

    return False

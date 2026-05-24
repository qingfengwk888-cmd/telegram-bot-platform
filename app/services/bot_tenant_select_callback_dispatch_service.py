async def dispatch_bot_tenant_select_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    username: str,
    display_name: str,
    data: str,
    callback_id: str,
    session,
    bot,
    bot_id: str,
) -> bool:
    from app.services.tenant_select_buttons_callback_service import try_handle_tenant_select_buttons_callback
    from app.services.tenant_select_blacklist_callback_service import try_handle_tenant_select_blacklist_callback
    from app.services.tenant_select_welcome_callback_service import try_handle_tenant_select_welcome_callback
    from app.services.tenant_select_broadcast_callback_service import try_handle_tenant_select_broadcast_callback
    from app.services.tenant_remove_confirm_callback_service import try_handle_tenant_remove_confirm_callback

    if await try_handle_tenant_select_buttons_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_tenant_select_blacklist_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_tenant_select_welcome_callback(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        username=username,
        display_name=display_name,
        data=data,
        callback_id=callback_id,
        session=session,
    ):
        return True

    if await try_handle_tenant_select_broadcast_callback(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        username=username,
        display_name=display_name,
        data=data,
        callback_id=callback_id,
        session=session,
        bot=bot,
        bot_id=bot_id,
    ):
        return True

    if await try_handle_tenant_remove_confirm_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    return False

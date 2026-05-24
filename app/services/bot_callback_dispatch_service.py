async def dispatch_bot_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_user: dict,
    from_id: int,
    data: str,
    callback_id: str,
    username: str,
    display_name: str,
) -> bool:
    from app.services.bot_precheck_callback_dispatch_service import dispatch_bot_precheck_callback
    from app.services.bot_callback_rate_limit_service import resolve_bot_for_callback_and_check_rate_limit
    from app.services.bot_button_callback_service import try_handle_bot_button_callback
    from app.services.bot_manage_menu_callback_service import try_handle_bot_manage_menu_callback
    from app.services.bot_callback_session_loader_service import load_bot_callback_session
    from app.services.bot_tenant_select_callback_dispatch_service import dispatch_bot_tenant_select_callback
    from app.services.bot_remove_callback_dispatch_service import dispatch_bot_remove_callback
    from app.services.bot_session_action_callback_dispatch_service import dispatch_bot_session_action_callback

    if await dispatch_bot_precheck_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    handled, bot_id, bot = await resolve_bot_for_callback_and_check_rate_limit(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    )
    if handled:
        return True

    if await try_handle_bot_button_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_user=from_user,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        display_name=display_name,
        bot=bot,
    ):
        return True

    if await try_handle_bot_manage_menu_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    session = await load_bot_callback_session(
        from_id=from_id,
        data=data,
    )

    if await dispatch_bot_tenant_select_callback(
        callback_query=callback_query,
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

    if await dispatch_bot_remove_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    return await dispatch_bot_session_action_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        session=session,
        bot=bot,
    )

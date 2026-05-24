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
    from app.services.bot_noop_callback_service import try_handle_bot_noop_callback
    from app.services.bot_manage_back_to_list_callback_service import try_handle_bot_manage_back_to_list_callback
    from app.services.bot_blacklist_back_callback_service import try_handle_bot_blacklist_back_callback
    from app.services.bot_blacklist_detail_back_callback_service import try_handle_bot_blacklist_detail_back_callback
    from app.services.bot_callback_rate_limit_service import resolve_bot_for_callback_and_check_rate_limit
    from app.services.bot_button_callback_service import try_handle_bot_button_callback
    from app.services.bot_manage_menu_callback_service import try_handle_bot_manage_menu_callback
    from app.services.bot_callback_session_loader_service import load_bot_callback_session
    from app.services.bot_tenant_select_callback_dispatch_service import dispatch_bot_tenant_select_callback
    from app.services.bot_remove_cancel_callback_service import try_handle_bot_remove_cancel_callback
    from app.services.bot_select_callback_service import try_handle_bot_select_callback
    from app.services.bot_remove_callback_service import try_handle_bot_remove_callback
    from app.services.bot_callback_session_required_service import try_handle_missing_bot_callback_session
    from app.services.bot_button_flow_callback_service import try_handle_bot_button_flow_callback
    from app.services.bot_modify_submit_callback_service import try_handle_bot_modify_submit_callback
    from app.services.tenant_broadcast_callback_service import try_handle_tenant_broadcast_callback
    from app.services.bot_callback_unknown_action_service import answer_unknown_bot_callback_action

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

    if await try_handle_bot_remove_cancel_callback(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_bot_select_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    if await try_handle_bot_remove_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    if await try_handle_missing_bot_callback_session(
        platform_bot_token=platform_bot_token,
        callback_id=callback_id,
        session=session,
    ):
        return True

    if await try_handle_bot_button_flow_callback(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        session=session,
        bot=bot,
    ):
        return True

    if await try_handle_bot_modify_submit_callback(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        session=session,
        bot=bot,
    ):
        return True

    if await try_handle_tenant_broadcast_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    await answer_unknown_bot_callback_action(
        platform_bot_token=platform_bot_token,
        callback_id=callback_id,
    )
    return True

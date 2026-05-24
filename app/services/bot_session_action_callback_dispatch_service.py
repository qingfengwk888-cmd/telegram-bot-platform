async def dispatch_bot_session_action_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    session,
    bot,
) -> bool:
    from app.services.bot_callback_session_required_service import try_handle_missing_bot_callback_session
    from app.services.bot_button_flow_callback_service import try_handle_bot_button_flow_callback
    from app.services.bot_modify_submit_callback_service import try_handle_bot_modify_submit_callback
    from app.services.tenant_broadcast_callback_service import try_handle_tenant_broadcast_callback
    from app.services.bot_callback_unknown_action_service import answer_unknown_bot_callback_action

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

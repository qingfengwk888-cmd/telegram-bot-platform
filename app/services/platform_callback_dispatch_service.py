async def dispatch_platform_callback(
    *,
    request,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app.services.platform_noop_callback_service import try_handle_platform_noop_callback
    from app.services.platform_callback_entry_dispatch_service import dispatch_platform_callback_entry
    from app.services.platform_apply_review_callback_service import try_handle_platform_apply_review_callback
    from app.services.platform_broadcast_callback_dispatch_service import dispatch_platform_broadcast_callback
    from app.services.platform_tenant_admin_callback_dispatch_service import dispatch_platform_tenant_admin_callback
    from app.services.platform_admin_action_callback_dispatch_service import dispatch_platform_admin_action_callback

    if await dispatch_platform_callback_entry(
        request=request,
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
    ):
        return True

    if await dispatch_platform_broadcast_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_platform_noop_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
    ):
        return True

    if await dispatch_platform_tenant_admin_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await dispatch_platform_admin_action_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
    ):
        return True

    if await try_handle_platform_apply_review_callback(
        request=request,
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    return False

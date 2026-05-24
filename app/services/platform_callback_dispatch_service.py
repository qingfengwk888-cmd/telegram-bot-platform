async def dispatch_platform_callback(
    *,
    request,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app.services.platform_secondary_admin_guard_service import try_block_secondary_admin_platform_callback
    from app.services.platform_bot_callback_router_service import try_route_platform_bot_callback
    from app.services.platform_admin_permission_guard_service import try_block_non_platform_admin_callback
    from app.services.platform_noop_callback_service import try_handle_platform_noop_callback
    from app.services.admin_tenant_menu_callback_service import try_handle_admin_tenant_menu_callback
    from app.services.platform_ad_pick_callback_service import try_handle_platform_ad_pick_callback
    from app.services.platform_ad_menu_callback_service import try_handle_platform_ad_menu_callback
    from app.services.admin_tenant_broadcast_start_callback_service import try_handle_admin_tenant_broadcast_start_callback
    from app.services.tenant_black_toggle_callback_service import try_handle_tenant_black_toggle_callback
    from app.services.tenant_category_callback_service import try_handle_tenant_category_callback
    from app.services.admin_tenant_back_callback_service import try_handle_admin_tenant_back_callback
    from app.services.admin_tenant_sort_callback_service import try_handle_admin_tenant_sort_callback
    from app.services.admin_tenant_filter_callback_service import try_handle_admin_tenant_filter_callback
    from app.services.admin_tenant_view_callback_service import try_handle_admin_tenant_view_callback
    from app.services.platform_apply_review_callback_service import try_handle_platform_apply_review_callback
    from app.services.platform_broadcast_callback_dispatch_service import dispatch_platform_broadcast_callback

    if await try_block_secondary_admin_platform_callback(
        platform_bot_token=platform_bot_token,
        callback_query=callback_query,
        from_id=from_id,
        data=data,
    ):
        return True

    if await try_route_platform_bot_callback(
        callback_query=callback_query,
        request=request,
        data=data,
    ):
        return True

    if await try_block_non_platform_admin_callback(
        platform_bot_token=platform_bot_token,
        callback_query=callback_query,
        from_id=from_id,
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

    if await try_handle_admin_tenant_menu_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_platform_ad_pick_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
    ):
        return True

    if await try_handle_platform_ad_menu_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
    ):
        return True

    if await try_handle_admin_tenant_broadcast_start_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
    ):
        return True

    if await try_handle_tenant_black_toggle_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_tenant_category_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_admin_tenant_back_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_admin_tenant_sort_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_admin_tenant_filter_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_admin_tenant_view_callback(
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

from app.services.platform_ad_pick_callback_service import try_handle_platform_ad_pick_callback
from app.services.platform_ad_menu_callback_service import try_handle_platform_ad_menu_callback
from app.services.admin_tenant_broadcast_start_callback_service import try_handle_admin_tenant_broadcast_start_callback


async def dispatch_platform_admin_action_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
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

    return False

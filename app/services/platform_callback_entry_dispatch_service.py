from app.services.platform_secondary_admin_guard_service import try_block_secondary_admin_platform_callback
from app.services.platform_bot_callback_router_service import try_route_platform_bot_callback
from app.services.platform_admin_permission_guard_service import try_block_non_platform_admin_callback


async def dispatch_platform_callback_entry(
    *,
    request,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
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

    return False

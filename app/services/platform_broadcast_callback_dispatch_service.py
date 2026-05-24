from app.services.admin_tenant_broadcast_cancel_callback_service import try_handle_admin_tenant_broadcast_cancel_callback
from app.services.platform_global_broadcast_cancel_callback_service import try_handle_platform_global_broadcast_cancel_callback
from app.services.platform_global_broadcast_confirm_callback_service import try_handle_platform_global_broadcast_confirm_callback
from app.services.admin_tenant_broadcast_confirm_callback_service import try_handle_admin_tenant_broadcast_confirm_callback
from app.services.platform_global_broadcast_target_cancel_callback_service import try_handle_platform_global_broadcast_target_cancel_callback
from app.services.platform_global_broadcast_target_select_callback_service import try_handle_platform_global_broadcast_target_select_callback


async def dispatch_platform_broadcast_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    if await try_handle_admin_tenant_broadcast_cancel_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_platform_global_broadcast_cancel_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_platform_global_broadcast_confirm_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_admin_tenant_broadcast_confirm_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_platform_global_broadcast_target_cancel_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return True

    if await try_handle_platform_global_broadcast_target_select_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
    ):
        return True

    return False

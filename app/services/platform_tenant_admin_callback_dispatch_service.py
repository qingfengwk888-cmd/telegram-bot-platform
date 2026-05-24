from app.services.admin_tenant_menu_callback_service import try_handle_admin_tenant_menu_callback
from app.services.tenant_black_toggle_callback_service import try_handle_tenant_black_toggle_callback
from app.services.tenant_category_callback_service import try_handle_tenant_category_callback
from app.services.admin_tenant_back_callback_service import try_handle_admin_tenant_back_callback
from app.services.admin_tenant_sort_callback_service import try_handle_admin_tenant_sort_callback
from app.services.admin_tenant_filter_callback_service import try_handle_admin_tenant_filter_callback
from app.services.admin_tenant_view_callback_service import try_handle_admin_tenant_view_callback


async def dispatch_platform_tenant_admin_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    if await try_handle_admin_tenant_menu_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        data=data,
        message=message,
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

    return False

from app.core.request_helpers import get_platform_bot_token
from app.services.bot_callback_context_service import build_bot_callback_context
from app.services.bot_callback_dispatch_service import dispatch_bot_callback


async def handle_bot_callback_query(callback_query: dict, request) -> None:
    platform_bot_token = get_platform_bot_token()
    callback_context = build_bot_callback_context(callback_query=callback_query)
    from_user = callback_context["from_user"]
    from_id = callback_context["from_id"]
    data = callback_context["data"]
    callback_id = callback_context["callback_id"]
    username = callback_context["username"]
    display_name = callback_context["display_name"]

    if await dispatch_bot_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_user=from_user,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        username=username,
        display_name=display_name,
    ):
        return


async def try_route_platform_bot_callback(
    *,
    callback_query: dict,
    request,
    data: str,
) -> bool:
    if (
        data.startswith("bot_manage:")
        or data.startswith("bot_select:")
        or data.startswith("bot_remove:")
        or data.startswith("bot_remove_confirm:")
        or data == "bot_remove_cancel"
        or data.startswith("button_flow:")
        or data.startswith("modify_submit:")
        or data == "bot_noop"
        or data == "bot_blacklist_back"
        or data.startswith("bot_blacklist_back:")
        or data.startswith("button_manage:")
        or data.startswith("button_delete:")
        or data == "tenant_broadcast_confirm"
        or data == "tenant_broadcast_cancel"
    ):
        await handle_bot_callback_query(callback_query, request)
        return True

    return False

from app.services.tenant_my_bots_message_service import try_handle_tenant_my_bots_message
from app.services.tenant_apply_start_message_service import try_handle_tenant_apply_start_message
from app.services.tenant_blacklist_view_message_service import try_handle_tenant_blacklist_view_message
from app.services.tenant_broadcast_start_message_service import try_handle_tenant_broadcast_start_message
from app.services.tenant_help_message_service import try_handle_tenant_help_message
from app.services.tenant_language_pack_message_service import try_handle_tenant_language_pack_message
from app.services.tenant_modify_deprecated_message_service import try_handle_tenant_modify_deprecated_message
from app.services.tenant_create_bot_token_message_service import try_handle_tenant_create_bot_token_message
from app.services.tenant_modify_input_message_service import try_handle_tenant_modify_input_message
from app.services.platform_admin_tenant_broadcast_legacy_input_service import try_handle_platform_admin_tenant_broadcast_legacy_input
from app.services.tenant_broadcast_input_message_service import try_handle_tenant_broadcast_input_message


async def dispatch_platform_tenant_message(
    *,
    request,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    username: str,
    name_text: str,
    display_name: str,
    session: dict,
) -> bool:
    if await try_handle_tenant_my_bots_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_tenant_apply_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        display_name=display_name,
        name_text=name_text,
    ):
        return True

    if await try_handle_tenant_blacklist_view_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_tenant_broadcast_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_tenant_help_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_tenant_language_pack_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_tenant_modify_deprecated_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_tenant_create_bot_token_message(
        request=request,
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        display_name=display_name,
        name_text=name_text,
        session=session,
    ):
        return True

    if await try_handle_tenant_modify_input_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    if await try_handle_platform_admin_tenant_broadcast_legacy_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    if await try_handle_tenant_broadcast_input_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    return False

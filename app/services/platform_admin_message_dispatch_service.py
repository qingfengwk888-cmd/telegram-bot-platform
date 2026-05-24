from app.services.platform_admin_tenant_broadcast_input_service import try_handle_platform_admin_tenant_broadcast_input
from app.services.platform_global_broadcast_input_service import try_handle_platform_global_broadcast_input
from app.services.platform_dashboard_message_service import try_handle_platform_dashboard_message
from app.services.platform_tenant_list_menu_message_service import try_handle_platform_tenant_list_menu_message
from app.services.platform_global_broadcast_menu_message_service import try_handle_platform_global_broadcast_menu_message
from app.services.platform_ad_settings_message_service import try_handle_platform_ad_settings_message
from app.services.platform_users_command_service import try_handle_platform_users_command
from app.services.platform_broadcast_all_command_service import try_handle_platform_broadcast_all_command
from app.services.platform_broadcast_command_service import try_handle_platform_broadcast_command
from app.services.platform_admin_help_message_service import try_handle_platform_admin_help_message


async def dispatch_platform_admin_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    session: dict,
) -> bool:
    if await try_handle_platform_admin_tenant_broadcast_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    if await try_handle_platform_global_broadcast_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    if await try_handle_platform_dashboard_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_tenant_list_menu_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_global_broadcast_menu_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_ad_settings_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_users_command(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_broadcast_all_command(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_broadcast_command(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    await try_handle_platform_admin_help_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
    )
    return True

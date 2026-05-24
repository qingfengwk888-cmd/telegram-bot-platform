from app.core.request_helpers import get_platform_admin_chat_id
from app.utils.helpers import is_primary_platform_admin, is_secondary_platform_admin
from app.services.apply_service import load_apply_session
from app.services.platform_admin_interrupt_session_service import interrupt_platform_admin_input_session_if_needed
from app.services.platform_ad_config_input_service import try_handle_platform_ad_config_input
from app.services.platform_tenant_message_guard_service import check_platform_tenant_message_guard
from app.services.platform_start_message_service import try_handle_platform_start_message
from app.services.platform_secondary_admin_restricted_message_service import try_handle_platform_secondary_admin_restricted_message
from app.services.platform_cancel_message_service import try_handle_platform_cancel_message
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
from app.services.tenant_interrupt_session_service import interrupt_tenant_input_session_if_needed
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


async def dispatch_platform_message(
    *,
    request,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    username: str,
    name_text: str,
    display_name: str,
) -> bool:
    is_platform_admin = (
        is_primary_platform_admin(chat_id)
        or is_secondary_platform_admin(chat_id)
    )

    session = await load_apply_session(chat_id)
    session = await interrupt_platform_admin_input_session_if_needed(
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
        session=session,
    )

    if is_platform_admin and await try_handle_platform_ad_config_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    handled, current_tenant = await check_platform_tenant_message_guard(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
    )
    if handled:
        return True

    # =========================================================
    # 首页 / 角色菜单
    # =========================================================
    if await try_handle_platform_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
    ):
        return True

    if await try_handle_platform_secondary_admin_restricted_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    if await try_handle_platform_cancel_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True

    # =========================================================
    # 管理员功能区
    # =========================================================
    if is_platform_admin and await try_handle_platform_admin_tenant_broadcast_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    if is_platform_admin and await try_handle_platform_global_broadcast_input(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    if is_platform_admin:
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

    # =========================================================
    # 租户功能区
    # =========================================================
    session = await interrupt_tenant_input_session_if_needed(
        chat_id=chat_id,
        text=text,
        session=session,
        platform_bot_token=platform_bot_token,
    )

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

    # =========================================================
    # create mode：只有在这里才监听 Bot Token
    # =========================================================
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

    # =========================================================
    # modify mode
    # =========================================================
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

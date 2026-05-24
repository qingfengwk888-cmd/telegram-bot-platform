from app.utils.helpers import is_primary_platform_admin, is_secondary_platform_admin
from app.services.apply_service import load_apply_session
from app.services.platform_admin_interrupt_session_service import interrupt_platform_admin_input_session_if_needed
from app.services.platform_ad_config_input_service import try_handle_platform_ad_config_input
from app.services.platform_tenant_message_guard_service import check_platform_tenant_message_guard
from app.services.platform_start_message_service import try_handle_platform_start_message
from app.services.platform_secondary_admin_restricted_message_service import try_handle_platform_secondary_admin_restricted_message
from app.services.platform_cancel_message_service import try_handle_platform_cancel_message
from app.services.tenant_interrupt_session_service import interrupt_tenant_input_session_if_needed
from app.services.platform_tenant_message_dispatch_service import dispatch_platform_tenant_message
from app.services.platform_admin_message_dispatch_service import dispatch_platform_admin_message


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
    if is_platform_admin and await dispatch_platform_admin_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
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

    if await dispatch_platform_tenant_message(
        request=request,
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        name_text=name_text,
        display_name=display_name,
        session=session,
    ):
        return True

    return False

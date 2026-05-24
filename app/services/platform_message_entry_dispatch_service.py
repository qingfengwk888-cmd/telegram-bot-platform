from app.services.apply_service import load_apply_session
from app.services.platform_admin_interrupt_session_service import interrupt_platform_admin_input_session_if_needed
from app.services.platform_ad_config_input_service import try_handle_platform_ad_config_input
from app.services.platform_tenant_message_guard_service import check_platform_tenant_message_guard
from app.services.platform_start_message_service import try_handle_platform_start_message
from app.services.platform_secondary_admin_restricted_message_service import try_handle_platform_secondary_admin_restricted_message
from app.services.platform_cancel_message_service import try_handle_platform_cancel_message


async def dispatch_platform_message_entry(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    is_platform_admin: bool,
) -> tuple[bool, dict]:
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
        return True, session

    handled, current_tenant = await check_platform_tenant_message_guard(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
    )
    if handled:
        return True, session

    if await try_handle_platform_start_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
    ):
        return True, session

    if await try_handle_platform_secondary_admin_restricted_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True, session

    if await try_handle_platform_cancel_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
    ):
        return True, session

    return False, session

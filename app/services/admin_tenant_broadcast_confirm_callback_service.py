async def try_handle_admin_tenant_broadcast_confirm_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy
    from app.services.admin_tenant_broadcast_confirm_validation_service import (
        validate_admin_tenant_broadcast_confirm_session,
    )
    from app.services.admin_tenant_broadcast_execute_service import (
        execute_admin_tenant_broadcast,
    )
    from app.services.admin_tenant_broadcast_finish_service import (
        finish_admin_tenant_broadcast_confirm,
    )

    if data != "admin_tenant_broadcast_confirm":
        return False

    session = await legacy.load_apply_session(from_id)
    valid, tenant_id, broadcast_text, tenant, sender_bot, users = await validate_admin_tenant_broadcast_confirm_session(
        platform_bot_token=platform_bot_token,
        callback_query=callback_query,
        from_id=from_id,
        session=session,
    )
    if not valid:
        return True

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "开始群发",
    })

    success, failed = await execute_admin_tenant_broadcast(
        sender_bot=sender_bot,
        users=users,
        broadcast_text=broadcast_text,
    )

    await finish_admin_tenant_broadcast_confirm(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        message=message,
        tenant_id=tenant_id,
        tenant=tenant,
        sender_bot=sender_bot,
        users=users,
        success=success,
        failed=failed,
    )
    return True

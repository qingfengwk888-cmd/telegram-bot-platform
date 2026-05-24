async def try_handle_platform_global_broadcast_confirm_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy
    from app.services.platform_global_broadcast_confirm_validation_service import (
        validate_platform_global_broadcast_confirm_session,
    )
    from app.services.platform_global_broadcast_execute_service import (
        execute_platform_global_broadcast,
    )
    from app.services.platform_global_broadcast_finish_service import (
        finish_platform_global_broadcast_confirm,
    )

    if data != "platform_global_broadcast_confirm":
        return False

    session = await legacy.load_apply_session(from_id)
    valid, broadcast_text, target_type = await validate_platform_global_broadcast_confirm_session(
        platform_bot_token=platform_bot_token,
        callback_query=callback_query,
        from_id=from_id,
        session=session,
    )
    if not valid:
        return True

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "开始全部群发",
    })

    total_target, success, failed = await execute_platform_global_broadcast(
        platform_bot_token=platform_bot_token,
        broadcast_text=broadcast_text,
        target_type=target_type,
    )

    await finish_platform_global_broadcast_confirm(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        message=message,
        target_type=target_type,
        total_target=total_target,
        success=success,
        failed=failed,
    )
    return True

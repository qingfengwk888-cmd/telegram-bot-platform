import re


async def try_handle_platform_apply_review_callback(
    *,
    request,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy
    from app.services.platform_apply_review_validation_service import (
        load_and_validate_platform_apply_review,
    )
    from app.services.platform_apply_reject_callback_service import (
        try_handle_platform_apply_reject_callback,
    )
    from app.services.platform_apply_approve_callback_service import (
        try_handle_platform_apply_approve_callback,
    )

    match = re.match(r"^(approve|reject):(.+)$", data)
    if not match:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "未知操作",
            "show_alert": True,
        })
        return True

    action = match.group(1)
    apply_id = match.group(2)
    valid, apply = await load_and_validate_platform_apply_review(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        apply_id=apply_id,
    )
    if not valid:
        return True

    if await try_handle_platform_apply_reject_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        action=action,
        apply=apply,
        message=message,
    ):
        return True

    if await try_handle_platform_apply_approve_callback(
        request=request,
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        action=action,
        apply=apply,
        message=message,
    ):
        return True

    return False

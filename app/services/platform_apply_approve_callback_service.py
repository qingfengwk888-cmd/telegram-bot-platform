import logging


logger = logging.getLogger(__name__)


async def try_handle_platform_apply_approve_callback(
    *,
    request,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    action: str,
    apply: dict,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.services.platform_apply_approve_update_callback_service import (
        try_handle_platform_apply_approve_update_callback,
    )
    from app.services.platform_apply_approve_create_callback_service import (
        handle_platform_apply_approve_create_callback,
    )

    if action != "approve":
        return False

    try:
        if await try_handle_platform_apply_approve_update_callback(
            callback_query=callback_query,
            platform_bot_token=platform_bot_token,
            from_id=from_id,
            action=action,
            apply=apply,
            message=message,
        ):
            return True

        await handle_platform_apply_approve_create_callback(
            request=request,
            callback_query=callback_query,
            platform_bot_token=platform_bot_token,
            from_id=from_id,
            apply=apply,
            message=message,
        )
        return True

    except Exception as err:
        logger.exception("approve apply failed")
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "处理失败，查看日志",
            "show_alert": True,
        })

        if message.get("chat", {}).get("id"):
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": message["chat"]["id"],
                "text": (
                    "❌ 处理申请失败\n"
                    f"申请ID：{apply.get('applyId')}\n"
                    f"错误：{str(err)}"
                ),
            })
        return True

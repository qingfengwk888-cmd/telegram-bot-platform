async def try_block_non_platform_admin_callback(
    *,
    platform_bot_token: str,
    callback_query: dict,
    from_id: int,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import is_primary_platform_admin, is_secondary_platform_admin

    if is_primary_platform_admin(from_id) or is_secondary_platform_admin(from_id):
        return False

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "无权限操作",
        "show_alert": True,
    })
    return True

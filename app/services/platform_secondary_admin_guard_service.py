def is_secondary_admin_blocked_platform_callback(
    *,
    from_id: int,
    data: str,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import is_secondary_platform_admin

    if not is_secondary_platform_admin(from_id):
        return False

    return (
        data.startswith("platform_ad_menu:")
        or data.startswith("platform_ad_pick:")
        or data.startswith("platform_global_broadcast")
        or data.startswith("platform_global_broadcast_target:")
        or data.startswith("admin_tenant_broadcast:")
        or data == "admin_tenant_broadcast_confirm"
        or data == "admin_tenant_broadcast_cancel"
    )


async def try_block_secondary_admin_platform_callback(
    *,
    platform_bot_token: str,
    callback_query: dict,
    from_id: int,
    data: str,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import is_secondary_platform_admin

    if not is_secondary_admin_blocked_platform_callback(
        from_id=from_id,
        data=data,
    ):
        return False

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "❌ 你没有权限执行此操作",
        "show_alert": True,
    })
    return True

import re


async def try_handle_admin_tenant_view_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
    from app import legacy_app as legacy

    tenant_view_match = re.match(r"^admin_tenant:view:(.+)$", data)
    if not tenant_view_match:
        return False

    tenant_id = legacy.sanitize_tenant_id(tenant_view_match.group(1))
    tenant = await legacy.load_tenant(tenant_id)

    if not tenant:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "租户不存在或已删除",
            "show_alert": True,
        })
        return True

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "处理中...",
    })

    users = await legacy.list_started_users_by_tenant_id_for_admin(tenant_id)

    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": (
            (await legacy.format_tenant_summary_text(tenant))
            + "\n\n"
            + legacy.format_started_users_text(tenant, users)
            + "\n\n"
            + legacy.format_tenant_category_text(tenant)
        ),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": legacy.build_tenant_detail_action_buttons(tenant_id, from_id),
    })
    return True

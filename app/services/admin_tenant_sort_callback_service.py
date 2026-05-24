import re


async def try_handle_admin_tenant_sort_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy

    sort_match = re.match(r"^admin_tenant_sort:(asc|desc)$", data)
    if not sort_match:
        return False

    sort_type = sort_match.group(1)

    ids = await legacy.get_tenant_index()
    tenants = []

    for tenant_id in ids:
        tenant = await legacy.load_tenant(tenant_id)
        if not tenant:
            continue
        tenant["_started_count"] = int(tenant.get("startedUserCount") or 0)
        tenants.append(tenant)

    tenants.sort(
        key=lambda x: int(x.get("_started_count", 0)),
        reverse=(sort_type == "desc")
    )

    title = (
        "🏢 所有租户 · 按流量从高到低"
        if sort_type == "desc"
        else "🏢 所有租户 · 按流量从低到高"
    )

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已完成排序",
    })

    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return True

    await legacy.tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": legacy.format_simple_tenant_list_text(title, tenants),
        "parse_mode": "HTML",
        "reply_markup": legacy.build_admin_tenant_pick_buttons_with_back(
            tenants,
            "admin_tenant_back:traffic"
        ),
    })
    return True

import re


async def try_handle_admin_tenant_filter_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.services.tenant_service import get_tenant_index, load_tenant
    from app.services.platform_dashboard_view_service import format_simple_tenant_list_text
    from app.services.admin_tenant_list_pagination_service import clamp_page, slice_tenants_for_page, build_admin_tenant_paginated_pick_buttons

    filter_match = re.match(r"^admin_tenant_filter:category:(local|external|other|blacklisted)(?::(\\d+))?$", data)
    if not filter_match:
        return False

    category = filter_match.group(1)
    page = max(1, int(filter_match.group(2) or 1))

    ids = await get_tenant_index()
    tenants = []

    for tenant_id in ids:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            continue

        if category == "blacklisted":
            if tenant.get("isBlacklisted"):
                tenants.append(tenant)
        else:
            if tenant.get("isBlacklisted"):
                continue

            tenant_category = str(tenant.get("category") or "other")
            if tenant_category not in {"local", "external", "other"}:
                tenant_category = "other"

            if tenant_category == category:
                tenants.append(tenant)

    category_label_map = {
        "local": "招商(本)",
        "external": "招商(外)",
        "other": "其他",
        "blacklisted": "已拉黑",
    }
    category_label = category_label_map.get(category, "其他")

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": f"已筛选：{category_label}",
    })

    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return True

    page, total_pages = clamp_page(page, len(tenants))
    display_tenants = slice_tenants_for_page(tenants, page)
    title = f"🏢 所有租户 · 分类：{category_label}"
    page_title = (
        f"{title}\n📄 第 {page}/{total_pages} 页，共 {len(tenants)} 个租户"
        if total_pages > 1
        else title
    )

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": format_simple_tenant_list_text(
            page_title,
            display_tenants
        ),
        "parse_mode": "HTML",
        "reply_markup": build_admin_tenant_paginated_pick_buttons(
            tenants=display_tenants,
            page=page,
            total_pages=total_pages,
            callback_base=f"admin_tenant_filter:category:{category}",
            back_to="admin_tenant_back:category",
        ),
    })
    return True

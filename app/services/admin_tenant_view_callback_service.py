import re


async def try_handle_admin_tenant_view_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict | None = None,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id
    from app.services.tenant_service import load_tenant, list_started_users_by_tenant_id_for_admin
    from app.telegram.formatters import format_tenant_summary_text, format_started_users_text, format_tenant_category_text
    from app.telegram.keyboards import build_tenant_detail_action_buttons

    tenant_view_match = re.match(r"^admin_tenant:view:([^:]+)(?::(\d+))?$", data)
    if not tenant_view_match:
        return False

    tenant_id = sanitize_tenant_id(tenant_view_match.group(1))
    page = max(1, int(tenant_view_match.group(2) or 1))
    tenant = await load_tenant(tenant_id)

    if not tenant:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "租户不存在或已删除",
            "show_alert": True,
        })
        return True

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "处理中...",
    })

    users = await list_started_users_by_tenant_id_for_admin(tenant_id)

    page_size = 25
    total = len(users)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    start = (page - 1) * page_size
    end = start + page_size
    display_users = users[start:end]

    page_text = (
        f"\n\n📄 当前第 {page}/{total_pages} 页，共 {total} 条启动记录。"
        if total > page_size
        else ""
    )

    reply_markup = build_tenant_detail_action_buttons(tenant_id, from_id)
    keyboard = list((reply_markup or {}).get("inline_keyboard") or [])

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append({
                "text": "⬅️ 上一页",
                "callback_data": f"admin_tenant:view:{tenant_id}:{page - 1}",
            })
        nav_row.append({
            "text": f"{page}/{total_pages}",
            "callback_data": "platform_noop",
        })
        if page < total_pages:
            nav_row.append({
                "text": "下一页 ➡️",
                "callback_data": f"admin_tenant:view:{tenant_id}:{page + 1}",
            })
        keyboard.append(nav_row)

    reply_markup["inline_keyboard"] = keyboard

    payload = {
        "chat_id": from_id,
        "text": (
            (await format_tenant_summary_text(tenant))
            + "\n\n"
            + format_started_users_text(tenant, display_users)
            + page_text
            + "\n\n"
            + format_tenant_category_text(tenant)
        ),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": reply_markup,
    }

    if page > 1 and message and message.get("chat", {}).get("id") and message.get("message_id"):
        payload["chat_id"] = message["chat"]["id"]
        payload["message_id"] = message["message_id"]
        await tg(platform_bot_token, "editMessageText", payload)
    else:
        await tg(platform_bot_token, "sendMessage", payload)
    return True

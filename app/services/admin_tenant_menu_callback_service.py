import re


async def try_handle_admin_tenant_menu_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.telegram.keyboards import build_admin_tenant_traffic_sort_buttons, build_admin_tenant_category_buttons

    menu_match = re.match(r"^admin_tenant_menu:(traffic|category)$", data)
    if not menu_match:
        return False

    menu_type = menu_match.group(1)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "请选择具体方式",
    })

    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return True

    if menu_type == "traffic":
        await tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": "🏢 所有租户\n\n请选择流量排序方式：",
            "reply_markup": build_admin_tenant_traffic_sort_buttons(),
        })
        return True

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": "🏢 所有租户\n\n请选择租户分类：",
        "reply_markup": build_admin_tenant_category_buttons(),
    })
    return True

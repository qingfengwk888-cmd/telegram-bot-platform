import re


async def try_handle_platform_ad_menu_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
    from app import legacy_app as legacy

    menu_match = re.match(r"^platform_ad_menu:(add|edit|delete)$", data)
    if not menu_match:
        return False

    action = menu_match.group(1)

    if not (legacy.is_primary_platform_admin(from_id) or legacy.is_secondary_platform_admin(from_id)):
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "无权限操作",
            "show_alert": True,
        })
        return True

    if action == "add":
        await legacy.save_apply_session(from_id, {
            "mode": "platform_ad_config",
            "step": "ad_text_input",
            "action": "add",
        })

        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "请发送广告文案",
        })

        await legacy.tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                "请输入广告文案。\n\n"
                "要求：\n"
                "1. 只显示一行\n"
                "2. 不超过 20 个字\n"
                "3. 例如：联系官方招商"
            ),
        })
        return True

    if action == "edit":
        items = await legacy.list_platform_ads()
        if not items:
            await legacy.tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "当前没有广告可修改",
                "show_alert": True,
            })
            return True

        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "请选择要修改的广告",
        })

        await legacy.tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请选择要修改的广告：",
            "reply_markup": legacy.build_platform_ad_pick_buttons(items, "edit"),
        })
        return True

    if action == "delete":
        items = await legacy.list_platform_ads()
        if not items:
            await legacy.tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_query["id"],
                "text": "当前没有广告可删除",
                "show_alert": True,
            })
            return True

        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "请选择要删除的广告",
        })

        await legacy.tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请选择要删除的广告：",
            "reply_markup": legacy.build_platform_ad_pick_buttons(items, "delete"),
        })
        return True

    return False

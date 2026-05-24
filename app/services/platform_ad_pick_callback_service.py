import re


async def try_handle_platform_ad_pick_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
    from app.telegram.api import tg
    from app.services.apply_service import save_apply_session
    from app.services.platform_ad_service import get_platform_ad_by_id, list_platform_ads, save_platform_ads

    pick_match = re.match(r"^platform_ad_pick:(edit|delete):(.+)$", data)
    if not pick_match:
        return False

    action = pick_match.group(1)
    ad_id = pick_match.group(2)

    ad_item = await get_platform_ad_by_id(ad_id)
    if not ad_item:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "广告不存在或已删除",
            "show_alert": True,
        })
        return True

    if action == "edit":
        await save_apply_session(from_id, {
            "mode": "platform_ad_config",
            "step": "ad_text_input",
            "action": "edit",
            "adId": ad_id,
        })

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "请发送新的广告文案",
        })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                f"当前广告文案：{ad_item.get('text') or ''}\n"
                f"当前广告链接：{ad_item.get('url') or ''}\n\n"
                "请发送新的广告文案。"
            ),
        })
        return True

    if action == "delete":
        items = await list_platform_ads()
        new_items = [x for x in items if str(x.get('adId') or '') != ad_id]

        await save_platform_ads(new_items)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "广告已删除",
        })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": f"✅ 已删除广告：{ad_item.get('text') or ad_id}",
        })
        return True

    return False

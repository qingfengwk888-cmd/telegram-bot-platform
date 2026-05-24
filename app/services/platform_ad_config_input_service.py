import html
import re

from app.telegram.api import tg
from app.utils.helpers import now_ms, escape_html
from app.services.apply_service import clear_apply_session, save_apply_session
from app.services.ad_service import generate_ad_id
from app.services.platform_ad_service import list_platform_ads, save_platform_ads


async def try_handle_platform_ad_config_input(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    session: dict,
) -> bool:
    if not session or session.get("mode") != "platform_ad_config":
        return False

    step = session.get("step")

    if step == "ad_text_input":
        ad_text = text.strip()

        if not ad_text:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "广告文案不能为空，请重新输入。",
            })
            return True

        # 这里限制字数，你自己定，我先给你 20 个字
        if len(ad_text) > 20:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"广告文案不能超过 20 个字，当前 {len(ad_text)} 个字，请重新输入。",
            })
            return True

        session["adText"] = ad_text
        session["step"] = "ad_url_input"
        await save_apply_session(chat_id, session)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                f"广告文案已记录：{ad_text}\n\n"
                "请继续发送广告链接。\n"
            ),
        })
        return True

    if step == "ad_url_input":
        ad_url = text.strip()

        if not ad_url:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "广告链接不能为空，请重新输入。",
            })
            return True

        if not re.match(r"^https?://", ad_url) and not re.match(r"^tg://", ad_url) and not re.match(r"^https://t\.me/", ad_url):
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "广告链接格式不正确，请发送完整链接，例如：https://t.me/kaiyunwind",
            })
            return True

        ad_text = str(session.get("adText") or "").strip()
        if not ad_text:
            await clear_apply_session(chat_id)
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "广告文案丢失，请重新进入广告设置。",
            })
            return True

        items = await list_platform_ads()
        action = session.get("action") or "add"

        if action == "add":
            items.append({
                "adId": generate_ad_id(),
                "text": ad_text,
                "url": ad_url,
                "createdAt": now_ms(),
                "updatedAt": now_ms(),
            })

        elif action == "edit":
            ad_id = str(session.get("adId") or "").strip()
            new_items = []

            for item in items:
                if str(item.get("adId") or "").strip() == ad_id:
                    new_items.append({
                        **item,
                        "text": ad_text,
                        "url": ad_url,
                        "updatedAt": now_ms(),
                    })
                else:
                    new_items.append(item)

            items = new_items

        await save_platform_ads(items)

        action = session.get("action") or "add"
        action_text = "新增成功" if action == "add" else "修改成功"

        await clear_apply_session(chat_id)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                f"✅ 广告{action_text}\n\n"
                f"广告文案：{escape_html(ad_text)}\n"
                f"广告链接：{escape_html(ad_url)}\n\n"
                "显示效果：\n"
                "广告：\n"
                f'<a href="{html.escape(ad_url, quote=True)}">{escape_html(ad_text)}</a>'
            ),
            "parse_mode": "HTML",
            "link_preview_options": {
                "is_disabled": True
            },
        })
        return True

    return False

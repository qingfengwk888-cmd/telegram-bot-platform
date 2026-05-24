from app.telegram.api import tg
from app.telegram.keyboards import build_platform_ad_menu_buttons
from app.utils.helpers import escape_html
from app.services.platform_ad_service import list_platform_ads


async def try_handle_platform_ad_settings_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "📢 广告设置":
        return False

    items = await list_platform_ads()

    if not items:
        preview = "当前未设置广告。"
    else:
        lines = []
        for idx, item in enumerate(items[:10], start=1):
            lines.append(
                f"{idx}. {escape_html(item.get('text') or '')}\n"
                f"   {escape_html(item.get('url') or '')}"
            )
        preview = "\n\n".join(lines)

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "📢 广告设置\n\n"
            f"{preview}\n\n"
            "请选择操作："
        ),
        "parse_mode": "HTML",
        "reply_markup": build_platform_ad_menu_buttons(),
        "link_preview_options": {
            "is_disabled": True
        },
    })
    return True

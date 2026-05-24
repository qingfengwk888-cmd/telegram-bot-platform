import re
from typing import Optional

from app.services.bot_service import load_bot, pick_default_bot_for_tenant
from app.services.tenant_service import load_tenant
from app.telegram.api import tg
from app.telegram.keyboards import build_single_bot_action_buttons
from app.utils.helpers import sanitize_tenant_id


async def try_handle_bot_manage_menu_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    bot: Optional[dict] = None,
) -> bool:
    # 第一层：点击机器人名字进入第二层操作菜单（不依赖 session）
    m_manage = re.match(r"^tenant_manage:(.+)$", data)
    if m_manage:
        tenant_id = sanitize_tenant_id(m_manage.group(1))
        tenant = await load_tenant(tenant_id)

        if not tenant:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return True

        if int(tenant.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return True

        bot = await pick_default_bot_for_tenant(tenant_id)
        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "该租户下暂无可操作机器人",
                "show_alert": True,
            })
            return True

        bot_id = str(bot.get("botId") or "").strip()
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请选择操作",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return True

    m_manage = re.match(r"^bot_manage:(.+)$", data)
    if m_manage:
        bot_id = sanitize_tenant_id(m_manage.group(1))
        bot = bot or await load_bot(bot_id)

        if not bot:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不存在",
                "show_alert": True,
            })
            return True

        if int(bot.get("adminChatId", 0)) != int(from_id):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return True

        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请选择操作",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return True

    return False

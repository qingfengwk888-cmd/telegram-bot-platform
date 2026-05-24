import re
from typing import Optional

from app.services.apply_service import save_apply_session
from app.services.bot_service import load_bot, save_bot
from app.telegram.api import tg
from app.telegram.formatters import format_button_preview
from app.telegram.keyboards import (
    build_button_delete_pick_buttons,
    build_button_manage_menu_buttons,
    build_single_bot_action_buttons,
    flatten_welcome_buttons,
    rebuild_button_rows,
)
from app.utils.helpers import now_ms, sanitize_tenant_id


async def try_handle_bot_button_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_user: dict,
    from_id: int,
    data: str,
    callback_id: str,
    display_name: str,
    bot: Optional[dict] = None,
) -> bool:
    m_button_add = re.match(r"^button_manage:add:(.+)$", data)
    if m_button_add:
        bot_id = sanitize_tenant_id(m_button_add.group(1))
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

        session = {
            "mode": "modify",
            "step": "button_text_input",
            "botId": bot_id,
            "tenantId": bot.get("tenantId") or "",
            "tenantName": bot.get("tenantName") or bot.get("tenantId") or "",
            "fieldKey": "welcomeButtons",
            "fieldLabel": "按钮",
            "applicantChatId": from_id,
            "applicantUsername": (from_user.get("username") or ""),
            "applicantDisplayName": display_name,
            "buttonDrafts": bot.get("welcomeButtons") or [],
            "currentButtonText": "",
            "currentButtonReply": "",
            "newValue": bot.get("welcomeButtons") or [],
        }
        await save_apply_session(from_id, session)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "开始添加按钮",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请发送按钮名称。",
        })
        return True

    m_button_delete_menu = re.match(r"^button_manage:delete:(.+)$", data)
    if m_button_delete_menu:
        bot_id = sanitize_tenant_id(m_button_delete_menu.group(1))
        bot = await load_bot(bot_id)

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

        buttons = bot.get("welcomeButtons") or []
        flat_buttons = flatten_welcome_buttons(buttons)

        if not flat_buttons:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "当前没有可删除的按钮",
                "show_alert": True,
            })
            return True

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "请选择要删除的按钮",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请选择要删除的按钮：",
            "reply_markup": build_button_delete_pick_buttons(bot_id, buttons),
        })
        return True

    m_button_delete = re.match(r"^button_delete:([^:]+):(\d+)$", data)
    if m_button_delete:
        bot_id = sanitize_tenant_id(m_button_delete.group(1))
        delete_index = int(m_button_delete.group(2))

        bot = await load_bot(bot_id)
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

        flat_buttons = flatten_welcome_buttons(bot.get("welcomeButtons") or [])
        if delete_index < 0 or delete_index >= len(flat_buttons):
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "按钮不存在",
                "show_alert": True,
            })
            return True

        deleted_name = str(flat_buttons[delete_index].get("text") or "").strip()
        del flat_buttons[delete_index]

        bot["welcomeButtons"] = rebuild_button_rows(flat_buttons)
        bot["updatedAt"] = now_ms()
        await save_bot(bot)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": f"已删除：{deleted_name}",
        })

        if flat_buttons:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"✅ 已删除按钮：{deleted_name}\n\n{format_button_preview(bot['welcomeButtons'])}",
                "reply_markup": build_button_delete_pick_buttons(bot_id, bot["welcomeButtons"]),
            })
        else:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": f"✅ 已删除按钮：{deleted_name}\n当前已无按钮。",
                "reply_markup": build_button_manage_menu_buttons(bot_id),
            })
        return True

    m_button_menu = re.match(r"^button_manage:menu:(.+)$", data)
    if m_button_menu:
        bot_id = sanitize_tenant_id(m_button_menu.group(1))
        bot = await load_bot(bot_id)

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
            "text": "返回按钮菜单",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_button_manage_menu_buttons(bot_id),
        })
        return True

    m_button_back = re.match(r"^button_manage:back:(.+)$", data)
    if m_button_back:
        bot_id = sanitize_tenant_id(m_button_back.group(1))
        bot = await load_bot(bot_id)

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
            "text": "返回上一级",
        })

        await tg(platform_bot_token, "editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": f"当前机器人：{show_name}",
            "reply_markup": build_single_bot_action_buttons(bot_id),
        })
        return True

    return False

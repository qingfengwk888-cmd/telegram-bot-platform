from typing import Optional

from app.services.apply_service import clear_apply_session, save_apply_session
from app.services.bot_service import load_bot, save_bot
from app.telegram.api import tg
from app.utils.helpers import now_ms, sanitize_tenant_id


async def try_handle_bot_button_flow_callback(
    *,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    session: dict,
    bot: Optional[dict] = None,
) -> bool:
    if data == "button_flow:add_more":
        session["step"] = "button_text_input"
        session["currentButtonText"] = ""
        session["currentButtonReply"] = ""
        await save_apply_session(from_id, session)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "继续添加",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "请发送下一个按钮名称。",
        })
        return True

    if data == "button_flow:finish":
        bot_id = sanitize_tenant_id(session.get("botId") or "")
        if not bot_id:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人无效",
                "show_alert": True,
            })
            return True

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
                "text": "无权限修改该机器人",
                "show_alert": True,
            })
            return True

        buttons = session.get("buttonDrafts") or []
        bot["welcomeButtons"] = buttons if isinstance(buttons, list) else []
        bot["updatedAt"] = now_ms()
        await save_bot(bot)
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "按钮已保存",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "✅ 按钮已生效，请重新 /start 你的机器人即可。",
        })
        return True

    if data == "button_flow:cancel":
        await clear_apply_session(from_id)
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "✅ 已取消当前按钮设置流程。",
        })
        return True

    return False

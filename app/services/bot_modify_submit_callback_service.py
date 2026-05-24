from typing import Optional

from app.services.apply_service import clear_apply_session, save_apply_session
from app.services.bot_service import load_bot, save_bot
from app.telegram.api import tg
from app.utils.helpers import now_ms, sanitize_tenant_id


async def try_handle_bot_modify_submit_callback(
    *,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    session: dict,
    bot: Optional[dict] = None,
) -> bool:
    if data == "modify_submit:cancel":
        await clear_apply_session(from_id)
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": "✅ 已取消当前修改流程。",
        })
        return True

    if data == "modify_submit:retry":
        if session.get("fieldKey") == "welcomeText":
            session["step"] = "welcome_text_input"
            session["newValue"] = ""
            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请重新填写欢迎语",
            })
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请重新发送新的欢迎语内容。",
            })
            return True

        if session.get("fieldKey") == "welcomeButtons":
            session["step"] = "button_text_input"
            session["buttonDrafts"] = []
            session["currentButtonText"] = ""
            session["currentButtonReply"] = ""
            session["newValue"] = []
            await save_apply_session(from_id, session)

            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "请重新设置按钮",
            })
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": from_id,
                "text": "请重新发送第一个按钮名称。",
            })
            return True

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "当前内容不支持重试",
            "show_alert": True,
        })
        return True

    if data == "modify_submit:confirm":
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

        field_key = str(session.get("fieldKey") or "").strip()
        new_value = session.get("newValue")

        if field_key == "welcomeText":
            bot["welcomeText"] = str(new_value or "").strip()
        elif field_key == "welcomeButtons":
            bot["welcomeButtons"] = new_value if isinstance(new_value, list) else []
        else:
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "当前字段不支持直接保存",
                "show_alert": True,
            })
            return True

        bot["updatedAt"] = now_ms()
        await save_bot(bot)
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "保存成功",
        })
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": f"✅ {session.get('fieldLabel') or '内容'} 已保存并立即生效。",
        })
        return True

    return False

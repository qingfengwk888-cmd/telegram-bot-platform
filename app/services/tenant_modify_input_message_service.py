from app.telegram.api import tg
from app.services.apply_service import save_apply_session
from app.telegram.formatters import format_button_preview
from app.telegram.keyboards import build_modify_confirm_buttons, build_button_flow_action_buttons


async def try_handle_tenant_modify_input_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    session: dict,
) -> bool:
    if not session or session.get("mode") != "modify":
        return False

    if session.get("step") == "welcome_text_input":
        session["newValue"] = text
        session["step"] = "modify_confirm"
        await save_apply_session(chat_id, session)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                f"请确认修改申请：\n\n"
                f"租户：{session['tenantId']}\n"
                f"字段：{session['fieldLabel']}\n"
                f"新值：\n{session['newValue']}"
            ),
            "reply_markup": build_modify_confirm_buttons(),
        })
        return True

    if session.get("step") == "button_text_input":
        session["currentButtonText"] = text.strip()
        session["currentButtonReply"] = ""
        session["step"] = "button_reply_input"
        await save_apply_session(chat_id, session)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"请发送按钮“{session['currentButtonText']}”点击后要回复的内容。",
        })
        return True

    if session.get("step") == "button_reply_input":
        btn_text = str(session.get("currentButtonText") or "").strip()
        btn_reply = text.strip()

        if not btn_text:
            session["step"] = "button_text_input"
            session["currentButtonReply"] = ""
            await save_apply_session(chat_id, session)
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "按钮名称丢失了，请重新发送按钮名称。",
            })
            return True

        drafts = session.get("buttonDrafts") or []
        drafts.append([{
            "text": btn_text,
            "reply": btn_reply,
        }])

        session["buttonDrafts"] = drafts
        session["newValue"] = drafts
        session["currentButtonText"] = ""
        session["currentButtonReply"] = ""
        session["step"] = "button_more_action"
        await save_apply_session(chat_id, session)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                f"已添加按钮：{btn_text}\n"
                f"回复内容：{btn_reply}\n\n"
                f"{format_button_preview(drafts)}\n\n"
                "请选择下一步："
            ),
            "reply_markup": build_button_flow_action_buttons(),
        })
        return True

    return False

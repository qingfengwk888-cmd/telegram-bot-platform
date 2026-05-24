import re


async def try_handle_tenant_select_welcome_callback(
    *,
    platform_bot_token: str,
    from_id: int,
    username: str,
    display_name: str,
    data: str,
    callback_id: str,
    session: dict | None,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id
    from app.services.tenant_service import load_tenant
    from app.services.apply_service import save_apply_session

    m = re.match(r"^tenant_select:welcome:(.+)$", data)
    if not m:
        return False

    tenant_id = sanitize_tenant_id(m.group(1))

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

    if not session:
        session = {
            "mode": "modify",
            "step": "",
            "applicantChatId": from_id,
            "applicantUsername": username,
            "applicantDisplayName": display_name,
            "tenantId": "",
            "tenantName": "",
            "botUsername": "",
            "fieldKey": "",
            "fieldLabel": "",
            "newValue": "",
            "buttonDrafts": [],
            "currentButtonText": "",
            "currentButtonReply": "",
        }

    bot_username = str(((tenant.get("botInfo") or {}).get("username") or "")).strip()

    session["tenantId"] = tenant_id
    session["tenantName"] = tenant.get("tenantName") or tenant_id
    session["botUsername"] = bot_username
    session["fieldKey"] = "welcomeText"
    session["fieldLabel"] = "欢迎语"
    session["step"] = "welcome_text_input"
    session["newValue"] = ""
    session["buttonDrafts"] = []
    session["currentButtonText"] = ""
    session["currentButtonReply"] = ""

    await save_apply_session(from_id, session)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "已选择机器人",
    })

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": f"你正在修改 @{bot_username or tenant_id} 的欢迎语。\n\n请直接发送新的欢迎语内容。",
    })
    return True

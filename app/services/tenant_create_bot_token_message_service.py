import asyncio

from app.telegram.api import tg, telegram_raw
from app.utils.helpers import build_bot_id_from_bot_username
from app.services.apply_service import clear_apply_session
from app.services.bot_service import load_bot
from app.services.bot_onboarding_service import create_bot_from_payload, get_or_create_tenant_by_admin
from app.core.request_helpers import get_platform_admin_chat_id
from app.services.platform_notice_view_service import notify_new_bot_connected


async def try_handle_tenant_create_bot_token_message(
    *,
    request,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    username: str,
    display_name: str,
    name_text: str,
    session: dict,
) -> bool:
    if not session or session.get("mode") != "create":
        return False

    if session.get("step") != "bot_token":
        return False

    bot_token = text.strip()
    me = await telegram_raw(bot_token, "getMe", {})
    if not me.get("ok"):
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": (
                "❌ Bot Token 校验失败，请确认后重新发送。\n\n"
                "提示：请发送形如 123456:ABC... 的完整 Token"
            ),
        })
        return True

    bot_info = me.get("result") or {}
    bot_username = str(bot_info.get("username") or "").strip()

    if not bot_username:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "❌ 机器人用户名获取失败，无法接入。",
        })
        return True

    bot_id = build_bot_id_from_bot_username(bot_username)
    exists = await load_bot(bot_id)
    if exists and str(exists.get("status") or "active") != "deleted":
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"❌ 机器人 @{bot_username} 已经接入过了，无需重复申请。",
        })
        return True

    tenant = await get_or_create_tenant_by_admin(
        chat_id,
        username=username,
        display_name=display_name,
    )

    tenant_name = username or name_text or f"user_{chat_id}"

    try:
        result = await create_bot_from_payload(
            request,
            {
                "tenantId": tenant["tenantId"],
                "tenantName": tenant.get("tenantName") or tenant_name,
                "botToken": bot_token,
                "botInfo": bot_info,
                "adminChatId": chat_id,
                "status": "active",
                "creatorUsername": username,
                "creatorName": display_name,
                "welcomeButtons": [],
            },
        )
    except Exception as err:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"❌ 接入失败：{str(err)}",
        })
        return True

    await clear_apply_session(chat_id)

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "✅ 接入成功\n\n"
            f"机器人：@{bot_username}\n"
        ),
    })

    platform_admin_chat_id = get_platform_admin_chat_id()
    tenant_id = result["tenant"]["tenantId"]
    bot = result["bot"]

    asyncio.create_task(
        notify_new_bot_connected(
            platform_bot_token=platform_bot_token,
            platform_admin_chat_id=platform_admin_chat_id,
            tenant_id=tenant_id,
            tenant_name=tenant.get("tenantName") or tenant_name,
            chat_id=chat_id,
            username=username,
            display_name=display_name,
            bot=bot,
        )
    )

    return True

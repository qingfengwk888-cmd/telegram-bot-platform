from fastapi import APIRouter, Request

from app.core.logger import logger
from app.core.request_helpers import get_platform_bot_token
from app.services.platform_blacklist_command_service import try_handle_platform_blacklist_command
from app.services.platform_callback_dispatch_service import dispatch_platform_callback
from app.services.platform_message_dispatch_service import dispatch_platform_message
from app.services.rate_limit_service import is_duplicate_update
from app.utils.helpers import json_response

router = APIRouter()


async def handle_platform_message(msg: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    username = (msg.get("from") or {}).get("username") or ""
    first_name = (msg.get("from") or {}).get("first_name") or ""
    last_name = (msg.get("from") or {}).get("last_name") or ""
    name_text = " ".join([x for x in [first_name, last_name] if x]).strip()
    display_name = f"@{username}" if username else (name_text or f"UID:{chat_id}")

    if await try_handle_platform_blacklist_command(msg):
        return

    if await dispatch_platform_message(
        request=request,
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        name_text=name_text,
        display_name=display_name,
    ):
        return


async def handle_platform_callback_query(callback_query: dict, request: Request) -> None:
    platform_bot_token = get_platform_bot_token()
    from_id = int((callback_query.get("from") or {}).get("id") or 0)
    data = str((callback_query.get("data") or "")).strip()
    message = callback_query.get("message") or {}

    if await dispatch_platform_callback(
        request=request,
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        message=message,
    ):
        return


@router.post("/platform/webhook")
async def platform_webhook(request: Request):
    """
    平台机器人 webhook 路由。

    当前阶段：
    - 路由逻辑已迁出旧单文件入口
    - 具体业务处理函数已拆分到 services
    """
    try:
        update = await request.json()

        if await is_duplicate_update("platform", update.get("update_id")):
            return {"ok": True, "ignored": "duplicate_update"}

        if update.get("callback_query"):
            await handle_platform_callback_query(update["callback_query"], request)
            return {"ok": True, "role": "platform_callback"}

        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return {"ok": True, "ignored": "no_message"}

        if (msg.get("chat") or {}).get("type") != "private":
            return {"ok": True, "ignored": "not_private"}

        await handle_platform_message(msg, request)
        return {"ok": True, "role": "platform_user"}

    except Exception as err:
        logger.exception("platform webhook error")
        return json_response({"ok": False, "error": str(err)}, 500)

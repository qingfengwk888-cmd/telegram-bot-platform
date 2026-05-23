from fastapi import APIRouter, Request

from app.core.logger import logger
from app.utils.helpers import json_response

router = APIRouter()


@router.post("/platform/webhook")
async def platform_webhook(request: Request):
    """
    平台机器人 webhook 路由。

    当前阶段：
    - 路由逻辑已经迁出 legacy_app
    - 具体业务处理函数仍临时调用 legacy_app
    """
    from app import legacy_app

    try:
        update = await request.json()

        if await legacy_app.is_duplicate_update("platform", update.get("update_id")):
            return {"ok": True, "ignored": "duplicate_update"}

        if update.get("callback_query"):
            await legacy_app.handle_platform_callback_query(update["callback_query"], request)
            return {"ok": True, "role": "platform_callback"}

        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return {"ok": True, "ignored": "no_message"}

        if (msg.get("chat") or {}).get("type") != "private":
            return {"ok": True, "ignored": "not_private"}

        await legacy_app.handle_platform_message(msg, request)
        return {"ok": True, "role": "platform_user"}

    except Exception as err:
        logger.exception("platform webhook error")
        return json_response({"ok": False, "error": str(err)}, 500)

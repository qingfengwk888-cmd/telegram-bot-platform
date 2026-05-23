from typing import Optional

from fastapi import APIRouter, Header, Request

router = APIRouter()


@router.post("/webhook/{bot_id}")
async def bot_webhook(
    bot_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    # 路由拆分过渡层：业务逻辑仍调用 legacy_app.bot_webhook
    # 必须透传 x_telegram_bot_api_secret_token，否则原函数会 401
    from app import legacy_app

    return await legacy_app.bot_webhook(
        bot_id=bot_id,
        request=request,
        x_telegram_bot_api_secret_token=x_telegram_bot_api_secret_token,
    )

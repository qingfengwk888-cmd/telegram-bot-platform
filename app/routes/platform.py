from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/platform/webhook")
async def platform_webhook(request: Request):
    # 临时过渡：路由拆出来，业务处理仍调用 legacy_app 里的原函数
    from app import legacy_app

    return await legacy_app.platform_webhook(request)

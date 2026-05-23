from typing import Optional

from fastapi import APIRouter, Header, Request

router = APIRouter()


@router.post("/internal/create-bot")
async def internal_create_bot(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app import legacy_app

    return await legacy_app.internal_create_bot(
        request=request,
        x_api_key=x_api_key,
        authorization=authorization,
    )


@router.post("/internal/setup-webhook")
async def internal_setup_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app import legacy_app

    return await legacy_app.internal_setup_webhook(
        request=request,
        x_api_key=x_api_key,
        authorization=authorization,
    )


@router.post("/internal/setup-platform-webhook")
async def internal_setup_platform_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app import legacy_app

    return await legacy_app.internal_setup_platform_webhook(
        request=request,
        x_api_key=x_api_key,
        authorization=authorization,
    )

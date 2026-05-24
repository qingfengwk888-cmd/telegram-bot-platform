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


@router.get("/internal/get-tenant")
async def internal_get_tenant(
    request: Request,
    tenantId: str,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_query_service import internal_get_tenant as handle_internal_get_tenant

    return await handle_internal_get_tenant(
        request=request,
        tenantId=tenantId,
        x_api_key=x_api_key,
        authorization=authorization,
    )


@router.get("/internal/list-tenants")
async def internal_list_tenants(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_query_service import internal_list_tenants as handle_internal_list_tenants

    return await handle_internal_list_tenants(
        x_api_key=x_api_key,
        authorization=authorization,
    )


@router.get("/internal/list-applies")
async def internal_list_applies(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_query_service import internal_list_applies as handle_internal_list_applies

    return await handle_internal_list_applies(
        x_api_key=x_api_key,
        authorization=authorization,
    )

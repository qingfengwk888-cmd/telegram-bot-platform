from typing import Optional

from fastapi import APIRouter, Header, Request

router = APIRouter()


@router.post("/internal/create-bot")
async def internal_create_bot(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_bot_create_service import internal_create_bot as handle_internal_create_bot

    return await handle_internal_create_bot(
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
    from app.services.internal_webhook_service import internal_setup_webhook as handle_internal_setup_webhook

    return await handle_internal_setup_webhook(
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
    from app.services.internal_webhook_service import internal_setup_platform_webhook as handle_internal_setup_platform_webhook

    return await handle_internal_setup_platform_webhook(
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



@router.post("/internal/delete-tenant")
async def internal_delete_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_tenant_admin_service import internal_delete_tenant as handle_internal_delete_tenant

    return await handle_internal_delete_tenant(
        request=request,
        x_api_key=x_api_key,
        authorization=authorization,
    )


@router.post("/internal/disable-tenant")
async def internal_disable_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_tenant_admin_service import internal_disable_tenant as handle_internal_disable_tenant

    return await handle_internal_disable_tenant(
        request=request,
        x_api_key=x_api_key,
        authorization=authorization,
    )


@router.post("/internal/enable-tenant")
async def internal_enable_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    from app.services.internal_tenant_admin_service import internal_enable_tenant as handle_internal_enable_tenant

    return await handle_internal_enable_tenant(
        request=request,
        x_api_key=x_api_key,
        authorization=authorization,
    )

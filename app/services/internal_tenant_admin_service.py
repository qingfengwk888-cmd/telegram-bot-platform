from typing import Optional

from fastapi import Header, Request

from app.core.request_helpers import require_internal_api_key
from app.core.responses import json_response
from app.services.tenant_service import load_tenant, save_tenant
from app.utils.helpers import sanitize_tenant_id, now_ms


async def internal_disable_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    tenant["status"] = "disabled"
    tenant["disabledAt"] = now_ms()
    await save_tenant(tenant)

    return {"ok": True, "tenantId": tenant_id, "status": tenant["status"]}


async def internal_enable_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    tenant["status"] = "active"
    tenant["enabledAt"] = now_ms()
    await save_tenant(tenant)

    return {"ok": True, "tenantId": tenant_id, "status": tenant["status"]}



async def internal_delete_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    body = await request.json()
    tenant_id = sanitize_tenant_id(body.get("tenantId") or "")
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    tenant["status"] = "deleted"
    tenant["deletedAt"] = now_ms()
    await save_tenant(tenant)

    return {"ok": True, "tenantId": tenant_id, "deleted": True}

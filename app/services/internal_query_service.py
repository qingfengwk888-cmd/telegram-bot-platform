from typing import Optional

from fastapi import Header, Request

from app.core.request_helpers import require_internal_api_key
from app.core.responses import json_response
from app.services.apply_service import get_apply_index, load_apply
from app.services.tenant_service import get_tenant_index, load_tenant
from app.utils.helpers import sanitize_tenant_id


async def internal_get_tenant(
    request: Request,
    tenantId: str,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    tenant_id = sanitize_tenant_id(tenantId)
    if not tenant_id:
        return json_response({"ok": False, "error": "tenantId_required"}, 400)

    tenant = await load_tenant(tenant_id)
    if not tenant:
        return json_response({"ok": False, "error": "tenant_not_found"}, 404)

    return {"ok": True, "tenant": tenant}


async def internal_list_tenants(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    ids = await get_tenant_index()
    tenants = []

    for tenant_id in ids:
        tenant = await load_tenant(tenant_id)
        if tenant:
            tenants.append({
                "tenantId": tenant.get("tenantId"),
                "tenantName": tenant.get("tenantName") or tenant.get("tenantId"),
                "status": tenant.get("status"),
                "adminChatId": tenant.get("adminChatId"),
                "detailUrl": tenant.get("detailUrl"),
                "createdAt": tenant.get("createdAt"),
                "approvedAt": tenant.get("approvedAt"),
                "updatedAt": tenant.get("updatedAt"),
            })

    return {"ok": True, "total": len(tenants), "tenants": tenants}


async def internal_list_applies(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not require_internal_api_key(x_api_key, authorization):
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    ids = await get_apply_index(100)
    applies = []

    for apply_id in ids:
        apply = await load_apply(apply_id)
        if apply:
            applies.append({
                "applyId": apply.get("applyId"),
                "type": apply.get("type") or "create",
                "status": apply.get("status"),
                "applicantChatId": apply.get("applicantChatId"),
                "applicantDisplayName": apply.get("applicantDisplayName"),
                "tenantName": apply.get("tenantName"),
                "tenantId": apply.get("tenantId"),
                "detailUrl": apply.get("detailUrl"),
                "updatePatch": apply.get("updatePatch"),
                "createdAt": apply.get("createdAt"),
                "reviewedAt": apply.get("reviewedAt"),
                "approvedTenantId": apply.get("approvedTenantId"),
            })

    return {"ok": True, "total": len(applies), "applies": applies}

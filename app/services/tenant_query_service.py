from typing import List, Optional

from app.services.tenant_service import get_tenant_index, load_tenant
from app.storage.repository import redis_get_json_db, redis_set_json_db


async def redis_get_json(key: str) -> Optional[dict]:
    return await redis_get_json_db(key)


async def redis_set_json(key: str, value: dict, ttl_seconds: Optional[int] = None) -> None:
    await redis_set_json_db(key, value, ttl_seconds)


async def list_tenants_by_admin_chat_id(admin_chat_id: int) -> List[dict]:
    ids = await get_tenant_index()
    tenants: List[dict] = []
    for tenant_id in ids:
        tenant = await load_tenant(tenant_id)
        if (
            tenant
            and int(tenant.get("adminChatId", 0)) == int(admin_chat_id)
            and str(tenant.get("status") or "active") != "deleted"
        ):
            tenants.append(tenant)
    return tenants

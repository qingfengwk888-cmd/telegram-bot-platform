from typing import Optional

from app.storage.redis_compat import redis_client
from app.storage.repository import redis_get_json_db, redis_set_json_db
from app.core.keys import tenant_data_key


async def acquire_short_lock(key: str, ttl: int = 3) -> bool:
    return bool(await redis_client.set(key, "1", ex=ttl, nx=True))


async def release_short_lock(key: str) -> None:
    await redis_client.delete(key)


async def set_current_lock(tenant_id: str, admin_chat_id: int, lock: dict, ttl_seconds: int = 3600) -> None:
    await redis_set_json_db(
        tenant_data_key(tenant_id, "lock", admin_chat_id),
        lock,
        ttl_seconds,
    )


async def get_current_lock(tenant_id: str, admin_chat_id: int) -> Optional[dict]:
    return await redis_get_json_db(tenant_data_key(tenant_id, "lock", admin_chat_id))


async def refresh_lock_if_current(
    tenant_id: str,
    admin_chat_id: int,
    expected_type: str,
    ttl_seconds: int = 3600,
) -> Optional[dict]:
    lock = await get_current_lock(tenant_id, admin_chat_id)
    if not lock:
        return None

    if str(lock.get("type") or "") != expected_type:
        return None

    await set_current_lock(tenant_id, admin_chat_id, lock, ttl_seconds)
    return lock

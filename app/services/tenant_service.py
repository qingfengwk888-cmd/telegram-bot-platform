import time
from typing import List, Optional

from app.core.logger import logger
from app.utils.helpers import (
    cost_ms,
    sanitize_tenant_id,
    build_tenant_id_from_admin_chat_id,
)
from app.storage.repository import (
    load_tenant_db,
    save_tenant_db,
    load_tenant_by_admin_chat_id_db,
    get_tenant_index_db,
    list_bots_by_tenant_id_db,
    list_started_users_by_tenant_id_db,
    refresh_tenant_today_started_user_count_db,
    set_platform_tenant_blacklisted_db,
    is_platform_tenant_blacklisted_db,
)



async def load_tenant(tenant_id: str) -> Optional[dict]:
    return await load_tenant_db(tenant_id)


async def save_tenant(tenant: dict) -> None:
    await save_tenant_db(tenant)


async def load_tenant_by_admin_chat_id(admin_chat_id: int) -> Optional[dict]:
    return await load_tenant_by_admin_chat_id_db(admin_chat_id)


async def get_tenant_index() -> List[str]:
    return await get_tenant_index_db()


async def add_tenant_index(tenant_id: str) -> None:
    # 数据库版不需要维护 Redis tenant:index
    return None


async def remove_tenant_index(tenant_id: str) -> None:
    # 数据库版不需要维护 Redis tenant:index
    return None


async def list_bots_by_tenant_id(tenant_id: str) -> List[dict]:
    start_ts = time.perf_counter()
    bots = await list_bots_by_tenant_id_db(tenant_id, include_deleted=False)
    logger.info(
        "perf list_bots_by_tenant_id tenant_id=%s loaded=%s cost_ms=%s source=db",
        tenant_id,
        len(bots),
        cost_ms(start_ts),
    )
    return bots


async def list_all_bots_by_tenant_id(tenant_id: str) -> List[dict]:
    start_ts = time.perf_counter()
    bots = await list_bots_by_tenant_id_db(tenant_id, include_deleted=True)
    logger.info(
        "perf list_all_bots_by_tenant_id tenant_id=%s loaded=%s cost_ms=%s source=db",
        tenant_id,
        len(bots),
        cost_ms(start_ts),
    )
    return bots


async def list_started_users_by_tenant_id(tenant_id: str) -> List[dict]:
    started = time.perf_counter()
    users = await list_started_users_by_tenant_id_db(tenant_id, include_deleted_bots=False)
    logger.info(
        "perf list_started_users_by_tenant_id tenant_id=%s users=%s cost_ms=%s source=db",
        tenant_id,
        len(users),
        cost_ms(started),
    )
    return users


async def list_started_users_by_tenant_id_for_admin(tenant_id: str) -> List[dict]:
    started = time.perf_counter()
    users = await list_started_users_by_tenant_id_db(tenant_id, include_deleted_bots=True)
    logger.info(
        "perf list_started_users_by_tenant_id_for_admin tenant_id=%s users=%s cost_ms=%s source=db",
        tenant_id,
        len(users),
        cost_ms(started),
    )
    return users


async def recompute_tenant_today_started_user_count(tenant_id: str) -> None:
    await refresh_tenant_today_started_user_count_db(tenant_id)


async def set_platform_tenant_blacklisted(tenant_id: str, value: bool) -> None:
    await set_platform_tenant_blacklisted_db(tenant_id, value)


async def is_platform_tenant_blacklisted(tenant_id: str) -> bool:
    return await is_platform_tenant_blacklisted_db(tenant_id)

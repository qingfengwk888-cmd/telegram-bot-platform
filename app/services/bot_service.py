import time
from typing import List, Optional

from app.core.logger import logger
from app.utils.helpers import (
    cost_ms,
    sanitize_tenant_id,
    build_bot_id_from_bot_username,
)
from app.storage.repository import (
    load_bot_db,
    save_bot_db,
    get_bot_index_db,
    get_latest_bot_id_by_tenant_id_db,
    list_started_users_by_bot_id_db,
    save_started_user_profile_db,
    set_bot_user_blacklisted_db,
    is_bot_user_blacklisted_db,
)


async def load_bot_by_bot_username(bot_username: str) -> Optional[dict]:
    bot_id = build_bot_id_from_bot_username(bot_username)
    return await load_bot(bot_id)


async def load_bot(bot_id: str) -> Optional[dict]:
    return await load_bot_db(bot_id)


async def save_bot(bot: dict) -> None:
    await save_bot_db(bot)


async def get_bot_index() -> List[str]:
    return await get_bot_index_db()


async def add_bot_index(bot_id: str) -> None:
    # 数据库版不需要维护 Redis bot:index
    return None


async def remove_bot_index(bot_id: str) -> None:
    # 数据库版不需要维护 Redis bot:index
    return None


async def pick_default_bot_for_tenant(tenant_id: str) -> Optional[dict]:
    latest_bot_id = await get_latest_bot_id_by_tenant_id_db(tenant_id)
    if not latest_bot_id:
        return None
    return await load_bot(latest_bot_id)


async def pick_sender_bot_for_tenant(tenant_id: str) -> Optional[dict]:
    return await pick_default_bot_for_tenant(tenant_id)


async def list_started_users(bot_id: str) -> List[dict]:
    started = time.perf_counter()
    users = await list_started_users_by_bot_id_db(bot_id)
    logger.info(
        "perf list_started_users bot_id=%s users=%s cost_ms=%s source=db",
        bot_id,
        len(users),
        cost_ms(started),
    )
    return users


async def save_started_user_profile(bot_id: str, user: dict) -> None:
    await save_started_user_profile_db(bot_id, user)


async def set_bot_user_blacklisted(bot_id: str, user_id: int, value: bool) -> None:
    await set_bot_user_blacklisted_db(bot_id, user_id, value)


async def is_bot_user_blacklisted(bot_id: str, user_id: int) -> bool:
    return await is_bot_user_blacklisted_db(bot_id, user_id)

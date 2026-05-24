from typing import Optional

from app.core.logger import logger
from app.core.keys import bot_stat_lock_key, tenant_stat_lock_key
from app.storage.redis_compat import redis_client
from app.services.bot_service import load_bot, save_bot
from app.services.tenant_service import load_tenant, save_tenant
from app.utils.helpers import get_today_ymd, is_same_ymd_ts_ms, now_ms


async def acquire_short_lock(key: str, ttl: int = 3) -> bool:
    return bool(await redis_client.set(key, "1", ex=ttl, nx=True))


async def release_short_lock(key: str) -> None:
    await redis_client.delete(key)


async def incr_bot_stat(
    bot_id: str,
    field: str,
    delta: int = 1,
    today_field: Optional[str] = None,
    ts_field: Optional[str] = None,
) -> None:
    lock_key = bot_stat_lock_key(bot_id, field)

    if not await acquire_short_lock(lock_key):
        return

    try:
        bot = await load_bot(bot_id)
        if not bot:
            return

        bot[field] = int(bot.get(field) or 0) + int(delta)

        if today_field:
            today_ymd = get_today_ymd()
            last_ts = int(bot.get(ts_field or "") or 0) if ts_field else 0

            if ts_field and not is_same_ymd_ts_ms(last_ts, today_ymd):
                bot[today_field] = 0

            bot[today_field] = int(bot.get(today_field) or 0) + int(delta)

            if ts_field:
                bot[ts_field] = now_ms()

        bot["updatedAt"] = now_ms()
        await save_bot(bot)

    except Exception:
        logger.exception("incr_bot_stat failed botId=%s field=%s", bot_id, field)

    finally:
        await release_short_lock(lock_key)


async def incr_tenant_stat(
    tenant_id: str,
    field: str,
    delta: int = 1,
    today_field: Optional[str] = None,
    ts_field: Optional[str] = None,
) -> None:
    lock_key = tenant_stat_lock_key(tenant_id, field)

    if not await acquire_short_lock(lock_key):
        return

    try:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            return

        tenant[field] = int(tenant.get(field) or 0) + int(delta)

        if today_field:
            today_ymd = get_today_ymd()
            last_ts = int(tenant.get(ts_field or "") or 0) if ts_field else 0

            if ts_field and not is_same_ymd_ts_ms(last_ts, today_ymd):
                tenant[today_field] = 0

            tenant[today_field] = int(tenant.get(today_field) or 0) + int(delta)

            if ts_field:
                tenant[ts_field] = now_ms()

        tenant["updatedAt"] = now_ms()
        await save_tenant(tenant)

    except Exception:
        logger.exception("incr_tenant_stat failed tenantId=%s field=%s", tenant_id, field)

    finally:
        await release_short_lock(lock_key)

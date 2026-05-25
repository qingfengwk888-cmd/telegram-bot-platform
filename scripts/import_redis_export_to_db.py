import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select, func
from app.storage.database import engine, AsyncSessionLocal
from app.storage.models import Base, Tenant, Bot, StartedUser, BotBlacklistUser, KVStore
from app.utils.helpers import now_ms, sanitize_tenant_id


EXPORT_PATH = ROOT_DIR / "redis_export.json"


def parse_json_maybe(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                return json.loads(s)
            except Exception:
                return value
    return value


def get_item_value(item: dict) -> Any:
    value = item.get("value")

    # redis_export.json 可能是两层结构：
    # {"key": "...", "value": {"type": "string", "ttl": -1, "value": "{...}"}}
    if isinstance(value, dict) and "value" in value and "type" in value:
        value = value.get("value")

    return parse_json_maybe(value)


async def upsert_tenant(session, tenant: dict) -> None:
    tenant_id = sanitize_tenant_id(tenant.get("tenantId") or "")
    if not tenant_id:
        return

    row = await session.get(Tenant, tenant_id)
    if not row:
        row = Tenant(tenant_id=tenant_id)
        session.add(row)

    row.tenant_name = str(tenant.get("tenantName") or tenant_id)
    row.admin_chat_id = int(tenant.get("adminChatId") or 0)
    row.creator_username = str(tenant.get("creatorUsername") or "").strip().lstrip("@")
    row.category = str(tenant.get("category") or "other")
    row.status = str(tenant.get("status") or "active")
    row.is_blacklisted = bool(tenant.get("isBlacklisted") or False)
    row.started_user_count = int(tenant.get("startedUserCount") or 0)
    row.today_started_user_count = int(tenant.get("todayStartedUserCount") or 0)
    row.created_at_ms = int(tenant.get("createdAt") or now_ms())
    row.updated_at_ms = int(tenant.get("updatedAt") or now_ms())
    row.data = dict(tenant)


async def upsert_bot(session, bot: dict) -> None:
    bot_id = sanitize_tenant_id(bot.get("botId") or "")
    if not bot_id:
        return

    bot_info = dict(bot.get("botInfo") or {})
    tenant_id = sanitize_tenant_id(bot.get("tenantId") or "")

    row = await session.get(Bot, bot_id)
    if not row:
        row = Bot(bot_id=bot_id)
        session.add(row)

    row.tenant_id = tenant_id
    row.bot_token = str(bot.get("botToken") or "")
    row.bot_username = str(bot_info.get("username") or "").strip().lstrip("@")
    row.tenant_name = str(bot.get("tenantName") or "")
    row.status = str(bot.get("status") or "active")
    row.started_user_count = int(bot.get("startedUserCount") or 0)
    row.blacklisted_user_count = int(bot.get("blacklistedUserCount") or 0)
    row.created_at_ms = int(bot.get("createdAt") or now_ms())
    row.updated_at_ms = int(bot.get("updatedAt") or now_ms())
    row.data = dict(bot)


async def upsert_started_user(session, bot_id: str, user: dict) -> None:
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user.get("userId") or 0)
    if not bot_id or not user_id:
        return

    bot = await session.get(Bot, bot_id)
    if not bot:
        return

    tenant_id = sanitize_tenant_id(user.get("tenantId") or bot.tenant_id or "")
    bot_username = str(
        user.get("botUsername")
        or ((dict(bot.data or {}).get("botInfo") or {}).get("username"))
        or bot.bot_username
        or ""
    ).strip().lstrip("@")

    stmt = select(StartedUser).where(
        StartedUser.bot_id == bot_id,
        StartedUser.user_id == user_id,
    )
    row = (await session.execute(stmt)).scalars().first()

    if not row:
        row = StartedUser(
            bot_id=bot_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        session.add(row)

    row.tenant_id = tenant_id
    row.username = str(user.get("username") or "").strip().lstrip("@")
    row.first_name = str(user.get("firstName") or "")
    row.last_name = str(user.get("lastName") or "")
    row.source = str(user.get("source") or "direct")
    row.bot_username = bot_username
    row.started_at_ms = int(user.get("startedAt") or now_ms())
    row.updated_at_ms = int(user.get("updatedAt") or now_ms())
    row.data = dict(user)


async def upsert_blacklist_user(session, bot_id: str, user_id: int) -> None:
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user_id)
    if not bot_id or not user_id:
        return

    stmt = select(BotBlacklistUser).where(
        BotBlacklistUser.bot_id == bot_id,
        BotBlacklistUser.user_id == user_id,
    )
    row = (await session.execute(stmt)).scalars().first()
    if not row:
        session.add(BotBlacklistUser(
            bot_id=bot_id,
            user_id=user_id,
            created_at_ms=now_ms(),
        ))


async def upsert_kv(session, key: str, item: dict) -> None:
    ttl = int(item.get("ttl") or -1)
    expire_at_ms = 0
    if ttl > 0:
        expire_at_ms = now_ms() + ttl * 1000

    value = item.get("value")
    if item.get("type") == "string":
        parsed = parse_json_maybe(value)
        if isinstance(parsed, dict):
            kv_value = parsed
        else:
            kv_value = {"value": parsed}
    elif item.get("type") == "set":
        kv_value = {"items": list(value or [])}
    elif item.get("type") == "list":
        kv_value = {"items": list(value or [])}
    elif item.get("type") == "hash":
        kv_value = dict(value or {})
    elif item.get("type") == "zset":
        kv_value = {"items": value or []}
    else:
        kv_value = {"value": value}

    row = await session.get(KVStore, key)
    if not row:
        row = KVStore(key=key)
        session.add(row)

    row.value = kv_value
    row.expire_at_ms = expire_at_ms


async def recompute_counts(session) -> None:
    bots = (await session.execute(select(Bot))).scalars().all()
    for bot in bots:
        started_count = await session.scalar(
            select(func.count(StartedUser.id)).where(StartedUser.bot_id == bot.bot_id)
        )
        black_count = await session.scalar(
            select(func.count(BotBlacklistUser.id)).where(BotBlacklistUser.bot_id == bot.bot_id)
        )
        bot.started_user_count = int(started_count or 0)
        bot.blacklisted_user_count = int(black_count or 0)
        bot.updated_at_ms = now_ms()

    tenants = (await session.execute(select(Tenant))).scalars().all()
    for tenant in tenants:
        started_count = await session.scalar(
            select(func.count(StartedUser.id)).where(StartedUser.tenant_id == tenant.tenant_id)
        )
        tenant.started_user_count = int(started_count or 0)
        tenant.updated_at_ms = now_ms()


async def main():
    if not EXPORT_PATH.exists():
        raise SystemExit(f"missing {EXPORT_PATH}")

    with EXPORT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stats = {
        "tenants": 0,
        "bots": 0,
        "started_users": 0,
        "blacklist_users": 0,
        "kv": 0,
        "skipped": 0,
    }

    async with AsyncSessionLocal() as session:
        # 1. tenants
        for key, item in data.items():
            if not re.match(r"^tenant:[^:]+$", key):
                continue
            value = get_item_value(item)
            if isinstance(value, dict) and value.get("tenantId"):
                await upsert_tenant(session, value)
                stats["tenants"] += 1

        await session.commit()

        # 2. bots
        for key, item in data.items():
            if not re.match(r"^bot:[^:]+$", key):
                continue
            value = get_item_value(item)
            if isinstance(value, dict) and value.get("botId"):
                await upsert_bot(session, value)
                stats["bots"] += 1

        await session.commit()

        # 3. started users
        for key, item in data.items():
            m = re.match(r"^b:([^:]+):profile:(\d+)$", key)
            if not m:
                continue
            bot_id, user_id = m.group(1), int(m.group(2))
            value = get_item_value(item)
            if isinstance(value, dict):
                value.setdefault("userId", user_id)
                await upsert_started_user(session, bot_id, value)
                stats["started_users"] += 1

        await session.commit()

        # 4. bot blacklist sets and markers
        for key, item in data.items():
            m_set = re.match(r"^b:([^:]+):black:users$", key)
            m_one = re.match(r"^b:([^:]+):black:user:(\d+)$", key)

            if m_set and item.get("type") == "set":
                bot_id = m_set.group(1)
                for uid in item.get("value") or []:
                    await upsert_blacklist_user(session, bot_id, int(uid))
                    stats["blacklist_users"] += 1

            elif m_one:
                bot_id, uid = m_one.group(1), int(m_one.group(2))
                await upsert_blacklist_user(session, bot_id, uid)
                stats["blacklist_users"] += 1

        await session.commit()

        # 5. keep useful compatibility keys in kv_store
        keep_kv_prefixes = (
            "t:",
            "platform:",
        )
        keep_exact = {
            "platform_ad_config",
            "tenant:index",
            "bot:index",
        }

        for key, item in data.items():
            if (
                key in keep_exact
                or key.startswith(keep_kv_prefixes)
                or re.match(r"^tenant:[^:]+:(bots|all_bots|latest_bot_id)$", key)
            ):
                await upsert_kv(session, key, item)
                stats["kv"] += 1

        await session.commit()

        await recompute_counts(session)
        await session.commit()

    print("✅ import finished")
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())

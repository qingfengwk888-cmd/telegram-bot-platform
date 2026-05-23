from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.storage.database import AsyncSessionLocal
from app.storage.models import Tenant, Bot, KVStore
from app.utils.helpers import now_ms, sanitize_tenant_id


def _tenant_to_dict(row: Tenant) -> dict:
    data = dict(row.data or {})
    data.update({
        "tenantId": row.tenant_id,
        "tenantName": row.tenant_name or data.get("tenantName") or row.tenant_id,
        "adminChatId": row.admin_chat_id,
        "creatorUsername": row.creator_username or data.get("creatorUsername", ""),
        "category": row.category or data.get("category", "other"),
        "status": row.status or data.get("status", "active"),
        "isBlacklisted": bool(row.is_blacklisted),
        "startedUserCount": int(row.started_user_count or 0),
        "todayStartedUserCount": int(row.today_started_user_count or 0),
        "createdAt": int(row.created_at_ms or data.get("createdAt") or 0),
        "updatedAt": int(row.updated_at_ms or data.get("updatedAt") or 0),
    })
    return data


def _bot_to_dict(row: Bot) -> dict:
    data = dict(row.data or {})
    bot_info = dict(data.get("botInfo") or {})
    if row.bot_username and not bot_info.get("username"):
        bot_info["username"] = row.bot_username

    data.update({
        "botId": row.bot_id,
        "tenantId": row.tenant_id,
        "botToken": row.bot_token or data.get("botToken", ""),
        "tenantName": row.tenant_name or data.get("tenantName", ""),
        "status": row.status or data.get("status", "active"),
        "startedUserCount": int(row.started_user_count or 0),
        "blacklistedUserCount": int(row.blacklisted_user_count or 0),
        "botInfo": bot_info,
        "createdAt": int(row.created_at_ms or data.get("createdAt") or 0),
        "updatedAt": int(row.updated_at_ms or data.get("updatedAt") or 0),
    })
    return data


async def redis_get_json_db(key: str) -> Optional[dict]:
    now = now_ms()
    async with AsyncSessionLocal() as session:
        row = await session.get(KVStore, key)
        if not row:
            return None

        if row.expire_at_ms and int(row.expire_at_ms) < now:
            await session.delete(row)
            await session.commit()
            return None

        return dict(row.value or {})


async def redis_set_json_db(key: str, value: dict, ttl_seconds: Optional[int] = None) -> None:
    expire_at_ms = 0
    if ttl_seconds:
        expire_at_ms = now_ms() + int(ttl_seconds) * 1000

    async with AsyncSessionLocal() as session:
        old = await session.get(KVStore, key)
        if old:
            old.value = value or {}
            old.expire_at_ms = expire_at_ms
        else:
            session.add(KVStore(
                key=key,
                value=value or {},
                expire_at_ms=expire_at_ms,
            ))
        await session.commit()


async def kv_delete_db(key: str) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(KVStore, key)
        if row:
            await session.delete(row)
            await session.commit()


async def load_tenant_db(tenant_id: str) -> Optional[dict]:
    tenant_id = sanitize_tenant_id(tenant_id)
    if not tenant_id:
        return None

    async with AsyncSessionLocal() as session:
        row = await session.get(Tenant, tenant_id)
        if not row:
            return None
        return _tenant_to_dict(row)


async def save_tenant_db(tenant: dict) -> None:
    tenant_id = sanitize_tenant_id(tenant.get("tenantId") or "")
    if not tenant_id:
        return

    data = dict(tenant or {})
    created_at = int(data.get("createdAt") or now_ms())
    updated_at = int(data.get("updatedAt") or now_ms())

    async with AsyncSessionLocal() as session:
        row = await session.get(Tenant, tenant_id)
        if not row:
            row = Tenant(tenant_id=tenant_id)
            session.add(row)

        row.tenant_name = str(data.get("tenantName") or tenant_id)
        row.admin_chat_id = int(data.get("adminChatId") or 0)
        row.creator_username = str(data.get("creatorUsername") or "").strip().lstrip("@")
        row.category = str(data.get("category") or "other")
        row.status = str(data.get("status") or "active")
        row.is_blacklisted = bool(data.get("isBlacklisted") or False)
        row.started_user_count = int(data.get("startedUserCount") or 0)
        row.today_started_user_count = int(data.get("todayStartedUserCount") or 0)
        row.created_at_ms = created_at
        row.updated_at_ms = updated_at
        row.data = data

        await session.commit()


async def load_bot_db(bot_id: str) -> Optional[dict]:
    bot_id = sanitize_tenant_id(bot_id)
    if not bot_id:
        return None

    async with AsyncSessionLocal() as session:
        row = await session.get(Bot, bot_id)
        if not row:
            return None
        return _bot_to_dict(row)


async def save_bot_db(bot: dict) -> None:
    bot_id = sanitize_tenant_id(bot.get("botId") or "")
    if not bot_id:
        return

    data = dict(bot or {})
    bot_info = dict(data.get("botInfo") or {})
    tenant_id = sanitize_tenant_id(data.get("tenantId") or "")
    created_at = int(data.get("createdAt") or now_ms())
    updated_at = int(data.get("updatedAt") or now_ms())

    async with AsyncSessionLocal() as session:
        row = await session.get(Bot, bot_id)
        if not row:
            row = Bot(bot_id=bot_id)
            session.add(row)

        row.tenant_id = tenant_id
        row.bot_token = str(data.get("botToken") or "")
        row.bot_username = str(bot_info.get("username") or "").strip().lstrip("@")
        row.tenant_name = str(data.get("tenantName") or "")
        row.status = str(data.get("status") or "active")
        row.started_user_count = int(data.get("startedUserCount") or 0)
        row.blacklisted_user_count = int(data.get("blacklistedUserCount") or 0)
        row.created_at_ms = created_at
        row.updated_at_ms = updated_at
        row.data = data

        await session.commit()


async def load_tenant_by_admin_chat_id_db(admin_chat_id: int) -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        stmt = select(Tenant).where(Tenant.admin_chat_id == int(admin_chat_id))
        row = (await session.execute(stmt)).scalars().first()
        if not row:
            return None
        return _tenant_to_dict(row)


async def get_tenant_index_db() -> List[str]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Tenant.tenant_id))).scalars().all()
        return sorted([str(x) for x in rows if x])


async def get_bot_index_db() -> List[str]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Bot.bot_id))).scalars().all()
        return sorted([str(x) for x in rows if x])


async def list_bot_ids_by_tenant_id_db(tenant_id: str, include_deleted: bool = False) -> List[str]:
    tenant_id = sanitize_tenant_id(tenant_id)

    async with AsyncSessionLocal() as session:
        stmt = select(Bot.bot_id).where(Bot.tenant_id == tenant_id)
        if not include_deleted:
            stmt = stmt.where(Bot.status != "deleted")
        rows = (await session.execute(stmt)).scalars().all()
        return sorted([str(x) for x in rows if x])


from sqlalchemy import and_
from app.storage.models import StartedUser, BotBlacklistUser


async def list_bots_by_tenant_id_db(tenant_id: str, include_deleted: bool = False) -> List[dict]:
    tenant_id = sanitize_tenant_id(tenant_id)
    if not tenant_id:
        return []

    async with AsyncSessionLocal() as session:
        stmt = select(Bot).where(Bot.tenant_id == tenant_id)
        if not include_deleted:
            stmt = stmt.where(Bot.status != "deleted")
        stmt = stmt.order_by(Bot.created_at_ms.desc())

        rows = (await session.execute(stmt)).scalars().all()
        return [_bot_to_dict(row) for row in rows]


async def list_started_users_by_tenant_id_db(tenant_id: str, include_deleted_bots: bool = False) -> List[dict]:
    tenant_id = sanitize_tenant_id(tenant_id)
    if not tenant_id:
        return []

    async with AsyncSessionLocal() as session:
        stmt = (
            select(StartedUser, Bot)
            .join(Bot, StartedUser.bot_id == Bot.bot_id)
            .where(StartedUser.tenant_id == tenant_id)
        )

        if not include_deleted_bots:
            stmt = stmt.where(Bot.status != "deleted")

        stmt = stmt.order_by(StartedUser.started_at_ms.desc())

        rows = (await session.execute(stmt)).all()

        results = []
        for user_row, bot_row in rows:
            data = dict(user_row.data or {})
            data.update({
                "botId": user_row.bot_id,
                "tenantId": user_row.tenant_id,
                "userId": int(user_row.user_id),
                "username": user_row.username or data.get("username", ""),
                "firstName": user_row.first_name or data.get("firstName", ""),
                "lastName": user_row.last_name or data.get("lastName", ""),
                "source": user_row.source or data.get("source", "direct"),
                "botUsername": user_row.bot_username or bot_row.bot_username or data.get("botUsername", ""),
                "startedAt": int(user_row.started_at_ms or data.get("startedAt") or 0),
                "updatedAt": int(user_row.updated_at_ms or data.get("updatedAt") or 0),
                "botStatus": bot_row.status or "active",
            })
            results.append(data)

        return results


async def list_started_users_by_bot_id_db(bot_id: str) -> List[dict]:
    bot_id = sanitize_tenant_id(bot_id)
    if not bot_id:
        return []

    async with AsyncSessionLocal() as session:
        stmt = (
            select(StartedUser)
            .where(StartedUser.bot_id == bot_id)
            .order_by(StartedUser.started_at_ms.desc())
        )

        rows = (await session.execute(stmt)).scalars().all()

        results = []
        for row in rows:
            data = dict(row.data or {})
            data.update({
                "botId": row.bot_id,
                "tenantId": row.tenant_id,
                "userId": int(row.user_id),
                "username": row.username or data.get("username", ""),
                "firstName": row.first_name or data.get("firstName", ""),
                "lastName": row.last_name or data.get("lastName", ""),
                "source": row.source or data.get("source", "direct"),
                "botUsername": row.bot_username or data.get("botUsername", ""),
                "startedAt": int(row.started_at_ms or data.get("startedAt") or 0),
                "updatedAt": int(row.updated_at_ms or data.get("updatedAt") or 0),
            })
            results.append(data)

        return results


async def save_started_user_profile_db(bot_id: str, user: dict) -> bool:
    """
    返回 True 表示新用户，False 表示老用户资料更新。
    """
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user.get("userId") or 0)
    if not bot_id or not user_id:
        return False

    bot = await load_bot_db(bot_id)
    if not bot:
        return False

    tenant_id = sanitize_tenant_id(bot.get("tenantId") or user.get("tenantId") or "")
    bot_username = str(
        user.get("botUsername")
        or ((bot.get("botInfo") or {}).get("username"))
        or ""
    ).strip().lstrip("@")

    async with AsyncSessionLocal() as session:
        stmt = select(StartedUser).where(
            and_(
                StartedUser.bot_id == bot_id,
                StartedUser.user_id == user_id,
            )
        )
        row = (await session.execute(stmt)).scalars().first()

        is_new = row is None
        old_data = dict(row.data or {}) if row else {}

        first_started_at = (
            old_data.get("startedAt")
            or (row.started_at_ms if row else 0)
            or user.get("startedAt")
            or now_ms()
        )

        merged = {
            **old_data,
            **user,
            "botId": bot_id,
            "tenantId": tenant_id,
            "botUsername": bot_username,
            "startedAt": int(first_started_at),
            "updatedAt": now_ms(),
        }

        if row is None:
            row = StartedUser(
                bot_id=bot_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            session.add(row)

        row.tenant_id = tenant_id
        row.username = str(merged.get("username") or "").strip().lstrip("@")
        row.first_name = str(merged.get("firstName") or "")
        row.last_name = str(merged.get("lastName") or "")
        row.source = str(merged.get("source") or "direct")
        row.bot_username = bot_username
        row.started_at_ms = int(first_started_at)
        row.updated_at_ms = now_ms()
        row.data = merged

        await session.commit()

    if is_new:
        bot["startedUserCount"] = int(bot.get("startedUserCount") or 0) + 1
        bot["updatedAt"] = now_ms()
        await save_bot_db(bot)

        if tenant_id:
            tenant = await load_tenant_db(tenant_id)
            if tenant:
                tenant["startedUserCount"] = int(tenant.get("startedUserCount") or 0) + 1

                today_ymd = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                started_ymd = __import__("datetime").datetime.fromtimestamp(
                    int(first_started_at) / 1000
                ).strftime("%Y-%m-%d")

                if started_ymd == today_ymd:
                    tenant["todayStartedUserCount"] = int(tenant.get("todayStartedUserCount") or 0) + 1

                tenant["updatedAt"] = now_ms()
                await save_tenant_db(tenant)

    return is_new


async def refresh_tenant_today_started_user_count_db(tenant_id: str) -> None:
    tenant_id = sanitize_tenant_id(tenant_id)
    if not tenant_id:
        return

    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    users = await list_started_users_by_tenant_id_db(tenant_id, include_deleted_bots=True)

    count = 0
    for u in users:
        started_at = int(u.get("startedAt") or 0)
        if not started_at:
            continue
        ymd = __import__("datetime").datetime.fromtimestamp(started_at / 1000).strftime("%Y-%m-%d")
        if ymd == today:
            count += 1

    tenant = await load_tenant_db(tenant_id)
    if tenant:
        tenant["todayStartedUserCount"] = count
        tenant["updatedAt"] = now_ms()
        await save_tenant_db(tenant)


async def get_latest_bot_id_by_tenant_id_db(tenant_id: str) -> Optional[str]:
    tenant_id = sanitize_tenant_id(tenant_id)
    if not tenant_id:
        return None

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Bot.bot_id)
            .where(Bot.tenant_id == tenant_id)
            .where(Bot.status != "deleted")
            .order_by(Bot.created_at_ms.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalars().first()


async def set_platform_tenant_blacklisted_db(tenant_id: str, value: bool) -> None:
    tenant = await load_tenant_db(tenant_id)
    if not tenant:
        return

    tenant["isBlacklisted"] = bool(value)
    tenant["category"] = "blacklisted" if value else str(tenant.get("category") or "other")
    tenant["updatedAt"] = now_ms()
    await save_tenant_db(tenant)


async def is_platform_tenant_blacklisted_db(tenant_id: str) -> bool:
    tenant = await load_tenant_db(tenant_id)
    return bool(tenant and tenant.get("isBlacklisted"))


async def set_bot_user_blacklisted_db(bot_id: str, user_id: int, value: bool) -> None:
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user_id)
    if not bot_id or not user_id:
        return

    async with AsyncSessionLocal() as session:
        stmt = select(BotBlacklistUser).where(
            and_(
                BotBlacklistUser.bot_id == bot_id,
                BotBlacklistUser.user_id == user_id,
            )
        )
        row = (await session.execute(stmt)).scalars().first()

        changed = False

        if value:
            if row is None:
                session.add(BotBlacklistUser(
                    bot_id=bot_id,
                    user_id=user_id,
                    created_at_ms=now_ms(),
                ))
                changed = True
        else:
            if row is not None:
                await session.delete(row)
                changed = True

        await session.commit()

    if changed:
        bot = await load_bot_db(bot_id)
        if bot:
            current = int(bot.get("blacklistedUserCount") or 0)
            bot["blacklistedUserCount"] = max(0, current + (1 if value else -1))
            bot["updatedAt"] = now_ms()
            await save_bot_db(bot)


async def is_bot_user_blacklisted_db(bot_id: str, user_id: int) -> bool:
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user_id)
    if not bot_id or not user_id:
        return False

    async with AsyncSessionLocal() as session:
        stmt = select(BotBlacklistUser.id).where(
            and_(
                BotBlacklistUser.bot_id == bot_id,
                BotBlacklistUser.user_id == user_id,
            )
        )
        return (await session.execute(stmt)).scalars().first() is not None


async def list_bot_blacklisted_users_db(bot_id: str) -> List[dict]:
    bot_id = sanitize_tenant_id(bot_id)
    if not bot_id:
        return []

    async with AsyncSessionLocal() as session:
        stmt = (
            select(BotBlacklistUser.user_id, StartedUser)
            .outerjoin(
                StartedUser,
                and_(
                    StartedUser.bot_id == BotBlacklistUser.bot_id,
                    StartedUser.user_id == BotBlacklistUser.user_id,
                )
            )
            .where(BotBlacklistUser.bot_id == bot_id)
            .order_by(BotBlacklistUser.created_at_ms.desc())
        )

        rows = (await session.execute(stmt)).all()

        results = []
        for uid, profile in rows:
            if profile:
                data = dict(profile.data or {})
                data.update({
                    "userId": int(uid),
                    "botId": bot_id,
                    "tenantId": profile.tenant_id,
                    "username": profile.username or data.get("username", ""),
                    "firstName": profile.first_name or data.get("firstName", ""),
                    "lastName": profile.last_name or data.get("lastName", ""),
                    "source": profile.source or data.get("source", "direct"),
                    "botUsername": profile.bot_username or data.get("botUsername", ""),
                    "startedAt": int(profile.started_at_ms or data.get("startedAt") or 0),
                })
            else:
                data = {
                    "userId": int(uid),
                    "botId": bot_id,
                    "username": "",
                    "firstName": "",
                    "lastName": "",
                    "source": "",
                    "botUsername": "",
                    "startedAt": 0,
                }
            results.append(data)

        return results

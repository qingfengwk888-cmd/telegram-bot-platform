    return "platform:ad:config"


async def load_platform_ad_config() -> Optional[dict]:
    return await redis_get_json(platform_ad_config_key())


async def save_platform_ad_config(data: dict) -> None:
    await redis_set_json(platform_ad_config_key(), data)

def generate_ad_id() -> str:
    return f"ad_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

async def list_platform_ads() -> List[dict]:
    data = await load_platform_ad_config()
    items = (data or {}).get("items") or []
    if not isinstance(items, list):
        return []
    return items

async def get_platform_ad_by_id(ad_id: str) -> Optional[dict]:
    items = await list_platform_ads()
    for item in items:
        if str(item.get("adId") or "") == str(ad_id):
            return item
    return None

async def save_platform_ads(items: List[dict]) -> None:
    await save_platform_ad_config({"items": items})

async def delete_platform_ad_config() -> None:
    await redis_client.delete(platform_ad_config_key())


async def redis_get_json(key: str) -> Optional[dict]:
    raw = await redis_client.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        logger.exception("failed parsing json from redis key=%s", key)
        return None


async def redis_set_json(key: str, value: dict, ttl_seconds: Optional[int] = None) -> None:
    payload = json.dumps(value, ensure_ascii=False)
    if ttl_seconds:
        await redis_client.set(key, payload, ex=ttl_seconds)
    else:
        await redis_client.set(key, payload)


async def load_tenant(tenant_id: str) -> Optional[dict]:
    tenant = await redis_get_json(tenant_key(tenant_id))
    if tenant and not tenant.get("tenantId"):
        tenant["tenantId"] = tenant_id
    return tenant


async def save_tenant(tenant: dict) -> None:
    await redis_set_json(tenant_key(tenant["tenantId"]), tenant)
    await upsert_tenant_index(tenant["tenantId"])


async def delete_tenant(tenant_id: str) -> None:
    await redis_client.delete(tenant_key(tenant_id))
    await remove_tenant_index(tenant_id)

async def load_bot(bot_id: str) -> Optional[dict]:
    start_ts = time.perf_counter()

    bot = await redis_get_json(bot_key(bot_id))

    logger.info(
        "perf load_bot bot_id=%s found=%s cost_ms=%s",
        bot_id,
        bool(bot),
        cost_ms(start_ts),
    )

    if bot and not bot.get("botId"):
        bot["botId"] = bot_id
    return bot

async def save_bot(bot: dict) -> None:
    bot["welcomeButtonReplyMap"] = build_button_reply_map(bot.get("welcomeButtons") or [])

    await redis_set_json(bot_key(bot["botId"]), bot)
    await redis_client.sadd(bot_index_key(), bot["botId"])
    await redis_client.sadd(tenant_bots_key(bot["tenantId"]), bot["botId"])
    await redis_client.sadd(tenant_all_bots_key(bot["tenantId"]), bot["botId"])

    tenant_id = str(bot.get("tenantId") or "").strip()
    bot_id = str(bot.get("botId") or "").strip()
    created_at = int(bot.get("createdAt") or 0)

    if tenant_id and bot_id:
        current_latest_bot_id = await redis_client.get(tenant_latest_bot_id_key(tenant_id))
        if not current_latest_bot_id:
            await redis_client.set(tenant_latest_bot_id_key(tenant_id), bot_id)
        elif current_latest_bot_id != bot_id:
            current_latest_bot = await load_bot(current_latest_bot_id)
            current_latest_created_at = int((current_latest_bot or {}).get("createdAt") or 0)
            if created_at >= current_latest_created_at:
                await redis_client.set(tenant_latest_bot_id_key(tenant_id), bot_id)

async def delete_bot(bot_id: str) -> None:
    bot = await load_bot(bot_id)
    tenant_id = str((bot or {}).get("tenantId") or "").strip()

    if tenant_id:
        await redis_client.srem(tenant_bots_key(tenant_id), bot_id)

    await redis_client.delete(bot_key(bot_id))
    await redis_client.srem(bot_index_key(), bot_id)

    if tenant_id:
        latest_bot_id = await redis_client.get(tenant_latest_bot_id_key(tenant_id))
        if latest_bot_id == bot_id:
            await refresh_tenant_latest_bot_id(tenant_id)


async def get_tenant_index() -> List[str]:
    ids = await redis_client.smembers(tenant_index_key())
    return sorted(list(ids or []))


async def upsert_tenant_index(tenant_id: str) -> None:
    await redis_client.sadd(tenant_index_key(), tenant_id)


async def remove_tenant_index(tenant_id: str) -> None:
    await redis_client.srem(tenant_index_key(), tenant_id)

async def load_tenant_by_admin_chat_id(admin_chat_id: int) -> Optional[dict]:
    tenant_id = build_tenant_id_from_admin_chat_id(admin_chat_id)
    return await load_tenant(tenant_id)


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


async def load_apply(apply_id: str) -> Optional[dict]:
    return await redis_get_json(apply_key(apply_id))


async def save_apply(apply: dict) -> None:
    key = apply_key(apply["applyId"])
    await redis_set_json(key, apply, APPLY_RECORD_TTL_SECONDS)
    await redis_client.lrem(apply_index_key(), 0, apply["applyId"])
    await redis_client.lpush(apply_index_key(), apply["applyId"])


async def get_apply_index(limit: int = 100) -> List[str]:

from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

def replace_func(name: str, new_body: str, async_func: bool = True):
    global text
    prefix = "async def" if async_func else "def"
    pattern = rf"\n{prefix} {name}\(.*?(?=\n(?:async def|def) )"
    text2, n = re.subn(pattern, "\n" + new_body.strip() + "\n\n", text, count=1, flags=re.S)
    print(f"{name}: replaced={n}")
    if n != 1:
        raise SystemExit(f"❌ 替换失败: {name}")
    text = text2

replace_func("list_bots_by_tenant_id", '''
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
''')

replace_func("list_all_bots_by_tenant_id", '''
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
''')

replace_func("list_started_users_by_tenant_id_for_admin", '''
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
''')

replace_func("save_started_user_profile", '''
async def save_started_user_profile(bot_id: str, user: dict) -> None:
    await save_started_user_profile_db(bot_id, user)
''')

replace_func("pick_default_bot_for_tenant", '''
async def pick_default_bot_for_tenant(tenant_id: str) -> Optional[dict]:
    latest_bot_id = await get_latest_bot_id_by_tenant_id_db(tenant_id)
    if not latest_bot_id:
        return None
    return await load_bot(latest_bot_id)
''')

replace_func("pick_sender_bot_for_tenant", '''
async def pick_sender_bot_for_tenant(tenant_id: str) -> Optional[dict]:
    return await pick_default_bot_for_tenant(tenant_id)
''')

replace_func("list_started_users_by_tenant_id", '''
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
''')

replace_func("list_started_users", '''
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
''')

replace_func("refresh_tenant_latest_bot_id", '''
async def refresh_tenant_latest_bot_id(tenant_id: str) -> None:
    # 数据库版不再需要单独维护 latest_bot_id key。
    # 最新 bot 通过 bots.created_at_ms 排序实时计算。
    return None
''')

replace_func("set_platform_tenant_blacklisted", '''
async def set_platform_tenant_blacklisted(tenant_id: str, value: bool) -> None:
    await set_platform_tenant_blacklisted_db(tenant_id, value)
''')

replace_func("is_platform_tenant_blacklisted", '''
async def is_platform_tenant_blacklisted(tenant_id: str) -> bool:
    return await is_platform_tenant_blacklisted_db(tenant_id)
''')

replace_func("set_bot_user_blacklisted", '''
async def set_bot_user_blacklisted(bot_id: str, user_id: int, value: bool) -> None:
    await set_bot_user_blacklisted_db(bot_id, user_id, value)
''')

replace_func("is_bot_user_blacklisted", '''
async def is_bot_user_blacklisted(bot_id: str, user_id: int) -> bool:
    return await is_bot_user_blacklisted_db(bot_id, user_id)
''')

replace_func("recompute_tenant_today_started_user_count", '''
async def recompute_tenant_today_started_user_count(tenant_id: str) -> None:
    await refresh_tenant_today_started_user_count_db(tenant_id)
''')

path.write_text(text, encoding="utf-8")
print("✅ core redis set functions patched to DB")

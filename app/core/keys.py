from app.utils.helpers import sanitize_tenant_id


def tenant_started_users_key(tenant_id: str) -> str:
    return f"t:{sanitize_tenant_id(tenant_id)}:started_users"


def bot_stat_lock_key(bot_id: str, name: str) -> str:
    return f"b:{bot_id}:stat_lock:{name}"


def tenant_stat_lock_key(tenant_id: str, name: str) -> str:
    return f"t:{sanitize_tenant_id(tenant_id)}:stat_lock:{name}"


def bot_started_users_key(bot_id: str) -> str:
    return f"b:{bot_id}:started_users"


def bot_start_alert_window_key(bot_id: str) -> str:
    return f"b:{bot_id}:start_alert_window"


def bot_start_alert_cooldown_key(bot_id: str) -> str:
    return f"b:{bot_id}:start_alert_cooldown"


def tenant_latest_bot_id_key(tenant_id: str) -> str:
    return f"t:{sanitize_tenant_id(tenant_id)}:latest_bot_id"


def tenant_key(tenant_id: str) -> str:
    return f"tenant:{sanitize_tenant_id(tenant_id)}"


def bot_key(bot_id: str) -> str:
    return f"bot:{sanitize_tenant_id(bot_id)}"


def bot_index_key() -> str:
    return "index:bots"


def tenant_bots_key(tenant_id: str) -> str:
    return f"t:{sanitize_tenant_id(tenant_id)}:bots"


def tenant_all_bots_key(tenant_id: str) -> str:
    return f"t:{sanitize_tenant_id(tenant_id)}:all_bots"


def tenant_index_key() -> str:
    return "index:tenants"


def tenant_data_key(tenant_id: str, *parts) -> str:
    safe_tenant_id = sanitize_tenant_id(tenant_id)
    tail = ":".join(str(p) for p in parts)
    return f"t:{safe_tenant_id}:data:{tail}"

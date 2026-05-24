from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "services" / "apply_service.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "generate_apply_id",
    "apply_key",
    "apply_index_key",
    "apply_session_key",
    "load_apply",
    "save_apply",
    "get_apply_index",
    "load_apply_session",
    "save_apply_session",
    "clear_apply_session",
    "create_bot_from_apply",
    "apply_bot_update",
]

blocks = []
missing = []

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    m = re.search(pattern, text, flags=re.S)
    if not m:
        missing.append(name)
        continue
    blocks.append(m.group(0).strip())

header = '''import time
import uuid
from typing import Optional, Dict, Any, List

from fastapi import Request

from app.config import APPLY_RECORD_TTL_SECONDS, APPLY_SESSION_TTL_SECONDS
from app.storage.repository import redis_get_json_db, redis_set_json_db, kv_delete_db
from app.storage.redis_compat import redis_client
from app.utils.helpers import escape_html, now_ms, sanitize_tenant_id, build_bot_id_from_bot_username
from app.telegram.api import tg, telegram_raw


# 兼容 legacy_app 旧函数名
redis_get_json = redis_get_json_db
redis_set_json = redis_set_json_db


def _legacy():
    from app import legacy_app
    return legacy_app


'''

content = header + "\n\n\n".join(blocks) + "\n"

# 处理抽出来函数里对 legacy_app 其他函数的直接依赖，先用懒加载兼容，避免循环导入
replacements = {
    "await load_bot(": "await _legacy().load_bot(",
    "await save_bot(": "await _legacy().save_bot(",
    "await load_tenant(": "await _legacy().load_tenant(",
    "await save_tenant(": "await _legacy().save_tenant(",
    "await load_tenant_by_admin_chat_id(": "await _legacy().load_tenant_by_admin_chat_id(",
    "await register_bot_commands_safe(": "await _legacy().register_bot_commands_safe(",
    "await notify_new_bot_connected(": "await _legacy().notify_new_bot_connected(",
    "await refresh_tenant_latest_bot_id(": "await _legacy().refresh_tenant_latest_bot_id(",
    "await recompute_tenant_today_started_user_count(": "await _legacy().recompute_tenant_today_started_user_count(",
    "build_bot_webhook_url(": "_legacy().build_bot_webhook_url(",
    "get_request_origin(": "_legacy().get_request_origin(",
    "generate_webhook_secret(": "_legacy().generate_webhook_secret(",
}

for old, new in replacements.items():
    content = content.replace(old, new)

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/services/apply_service.py")
print(f"blocks={len(blocks)}")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)

if not blocks:
    raise SystemExit("❌ 没抽到任何 apply 相关函数")

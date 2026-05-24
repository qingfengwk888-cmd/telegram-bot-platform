from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "services" / "tenant_service.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "build_tenant_id_from_admin_chat_id",
    "load_tenant",
    "save_tenant",
    "load_tenant_by_admin_chat_id",
    "get_tenant_index",
    "add_tenant_index",
    "remove_tenant_index",
    "list_bots_by_tenant_id",
    "list_all_bots_by_tenant_id",
    "list_started_users_by_tenant_id",
    "list_started_users_by_tenant_id_for_admin",
    "recompute_tenant_today_started_user_count",
    "set_platform_tenant_blacklisted",
    "is_platform_tenant_blacklisted",
    "format_tenant_category_text",
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

content = '''import time
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


''' + "\n\n\n".join(blocks) + "\n"

# 避免重复定义从 helpers import 的 build_tenant_id_from_admin_chat_id
content = re.sub(
    r"\n?def build_tenant_id_from_admin_chat_id\(.*?(?=\n(?:async def|def) )",
    "\n",
    content,
    count=1,
    flags=re.S,
)

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/services/tenant_service.py")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)

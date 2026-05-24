from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

import_block = '''
from app.storage.repository import (
    redis_get_json_db,
    redis_set_json_db,
    load_tenant_db,
    save_tenant_db,
    load_bot_db,
    save_bot_db,
    load_tenant_by_admin_chat_id_db,
    get_tenant_index_db,
    get_bot_index_db,
    list_bot_ids_by_tenant_id_db,
)
'''

if "from app.storage.repository import" not in text:
    text = text.replace("from fastapi.responses import JSONResponse\n", "from fastapi.responses import JSONResponse\n" + import_block + "\n")

replacements = {
    r"async def redis_get_json\(key: str\).*?(?=\nasync def redis_set_json\()": '''
async def redis_get_json(key: str) -> Optional[dict]:
    return await redis_get_json_db(key)
''',

    r"async def redis_set_json\(key: str, value: dict, ttl_seconds: Optional\[int\] = None\).*?(?=\nasync def load_tenant\()": '''
async def redis_set_json(key: str, value: dict, ttl_seconds: Optional[int] = None) -> None:
    await redis_set_json_db(key, value, ttl_seconds)
''',

    r"async def load_tenant\(tenant_id: str\).*?(?=\nasync def save_tenant\()": '''
async def load_tenant(tenant_id: str) -> Optional[dict]:
    return await load_tenant_db(tenant_id)
''',

    r"async def save_tenant\(tenant: dict\).*?(?=\nasync def load_bot\()": '''
async def save_tenant(tenant: dict) -> None:
    await save_tenant_db(tenant)
''',

    r"async def load_bot\(bot_id: str\).*?(?=\nasync def save_bot\()": '''
async def load_bot(bot_id: str) -> Optional[dict]:
    return await load_bot_db(bot_id)
''',

    r"async def save_bot\(bot: dict\).*?(?=\nasync def load_tenant_by_admin_chat_id\()": '''
async def save_bot(bot: dict) -> None:
    await save_bot_db(bot)
''',

    r"async def load_tenant_by_admin_chat_id\(admin_chat_id: int\).*?(?=\n(?:async def|def) )": '''
async def load_tenant_by_admin_chat_id(admin_chat_id: int) -> Optional[dict]:
    return await load_tenant_by_admin_chat_id_db(admin_chat_id)

''',
}

for pattern, repl in replacements.items():
    text, n = re.subn(pattern, repl.strip() + "\n", text, count=1, flags=re.S)
    print(f"{pattern[:60]}... replaced={n}")
    if n != 1:
        raise SystemExit(f"❌ 替换失败或匹配数量异常: {pattern}")

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py storage functions patched to DB")

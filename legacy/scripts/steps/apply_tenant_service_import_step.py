from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

names = [
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
]

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.services.tenant_service import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.services.tenant_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses tenant_service")

from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "bot_user_black_key",
    "bot_user_blacklist_set_key",
    "platform_tenant_black_key",
    "is_tenant_user_blacklisted",
    "list_blacklisted_users_by_tenant_id",
    "list_blacklisted_users",
    "format_blacklisted_users_text",
    "format_tenant_blacklisted_users_text",
]

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.services.blacklist_service import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.services.blacklist_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses blacklist_service")

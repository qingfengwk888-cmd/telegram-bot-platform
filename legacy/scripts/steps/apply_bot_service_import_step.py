from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

names = [
    "load_bot_by_bot_username",
    "list_started_users",
    "load_bot",
    "save_bot",
    "get_bot_index",
    "add_bot_index",
    "remove_bot_index",
    "pick_default_bot_for_tenant",
    "pick_sender_bot_for_tenant",
    "save_started_user_profile",
    "set_bot_user_blacklisted",
    "is_bot_user_blacklisted",
]

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.services.bot_service import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.services.bot_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses bot_service")

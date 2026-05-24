from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "find_bot_button_reply",
    "bot_user_profile_key",
    "check_bot_start_alert",
]

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = """from app.services.user_service import (
    find_bot_button_reply,
    bot_user_profile_key,
    check_bot_start_alert,
)
"""

if "from app.services.user_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses user_service")

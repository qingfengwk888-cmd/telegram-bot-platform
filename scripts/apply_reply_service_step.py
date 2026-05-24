from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "reply_rate_limited_for_callback",
    "reply_rate_limited_for_message",
]

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = """from app.services.reply_service import (
    reply_rate_limited_for_callback,
    reply_rate_limited_for_message,
)
"""

if "from app.services.reply_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses reply_service")

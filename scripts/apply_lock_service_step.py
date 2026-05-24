from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "acquire_short_lock",
    "release_short_lock",
    "set_current_lock",
    "get_current_lock",
    "refresh_lock_if_current",
]

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.services.lock_service import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.services.lock_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses lock_service")

from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "tenant_started_users_key",
    "bot_stat_lock_key",
    "tenant_stat_lock_key",
    "bot_started_users_key",
    "bot_start_alert_window_key",
    "bot_start_alert_cooldown_key",
    "tenant_latest_bot_id_key",
    "tenant_key",
    "bot_key",
    "bot_index_key",
    "tenant_bots_key",
    "tenant_all_bots_key",
    "tenant_index_key",
    "tenant_data_key",
]

for name in names:
    pattern = rf"\ndef {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.core.keys import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.core.keys import" not in text:
    text = text.replace(
        "from app.core.logger import logger\n",
        "from app.core.logger import logger\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses app.core.keys")

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

names = [
    "build_bot_pick_buttons",
    "build_my_bots_action_buttons",
    "build_button_flow_action_buttons",
    "build_global_broadcast_confirm_buttons",
    "build_global_broadcast_target_buttons",
    "build_modify_confirm_buttons",
    "build_my_bots_entry_buttons",
    "build_single_bot_action_buttons",
    "build_button_manage_menu_buttons",
    "build_button_delete_pick_buttons",
    "build_button_reply_map",
    "build_profile_buttons",
    "flatten_welcome_buttons",
    "rebuild_button_rows",
    "build_remove_confirm_buttons",
    "build_platform_reply_keyboard_for_admin",
    "build_bot_reply_keyboard",
    "build_platform_ad_menu_buttons",
    "build_platform_ad_pick_buttons",
    "build_platform_reply_keyboard_for_tenant",
    "build_admin_tenant_pick_buttons",
    "build_admin_tenant_root_menu_buttons",
    "build_admin_tenant_traffic_sort_buttons",
    "build_admin_tenant_category_buttons",
    "build_admin_tenant_pick_buttons_with_back",
    "build_tenant_category_buttons",
    "build_tenant_detail_category_buttons",
    "build_tenant_detail_action_buttons",
    "build_new_tenant_notice_buttons",
    "build_apply_approve_buttons",
    "build_welcome_buttons",
]

removed = []

for name in names:
    pattern = rf"\ndef {name}\(.*?(?=\n(?:async def|def) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")
    if n == 1:
        removed.append(name)

import_block = "from app.telegram.keyboards import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.telegram.keyboards import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1
    )

path.write_text(text, encoding="utf-8")

print(f"✅ removed {len(removed)} keyboard functions and added import")

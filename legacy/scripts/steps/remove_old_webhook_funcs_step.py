from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

def remove_func(name: str):
    global text
    pattern = rf"\n(?:# route moved to app\.routes\.[a-zA-Z_]+\n)?async def {name}\(.*?(?=\n(?:# route moved|@app\.|async def|def) )"
    text2, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")
    if n != 1:
        raise SystemExit(f"❌ 删除失败：{name}")
    text = text2

remove_func("platform_webhook")
remove_func("bot_webhook")

path.write_text(text, encoding="utf-8")
print("✅ old platform_webhook and bot_webhook removed from legacy_app.py")

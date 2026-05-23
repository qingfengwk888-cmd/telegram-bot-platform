from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

# 加 health router import
if "from app.routes.health import router as health_router" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\nfrom app.routes.health import router as health_router\n",
        1,
    )

# 删除 legacy_app.py 里旧的 /health 路由
patterns = [
    r'\n@app\.get\("/health"\)\nasync def health\(.*?\):\n(?:    .*\n)+',
    r'\n@app\.get\("/health"\)\nasync def health_check\(.*?\):\n(?:    .*\n)+',
]

removed = 0
for p in patterns:
    text, n = re.subn(p, "\n", text, count=1)
    removed += n

# 在 app = FastAPI(...) 后面 include router
marker = "app = FastAPI(title=APP_NAME, lifespan=lifespan)\n"
insert = "app.include_router(health_router)\n"

if insert not in text:
    if marker not in text:
        raise SystemExit("❌ 没找到 app = FastAPI(title=APP_NAME, lifespan=lifespan)")
    text = text.replace(marker, marker + insert, 1)

path.write_text(text, encoding="utf-8")

print(f"✅ health route split done, removed_old_health={removed}")

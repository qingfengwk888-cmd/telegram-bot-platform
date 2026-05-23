from dotenv import load_dotenv

load_dotenv()

# 临时入口：先直接挂原单文件应用，保证功能不被重写
from app.legacy_app import app

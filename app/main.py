from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.config import APP_NAME
from app.core.lifespan import lifespan
from app.routes.health import router as health_router
from app.routes.platform import router as platform_router
from app.routes.webhook import router as webhook_router
from app.routes.internal import router as internal_router


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.include_router(health_router)
app.include_router(platform_router)
app.include_router(webhook_router)
app.include_router(internal_router)

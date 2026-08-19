# FastAPI 应用入口

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """应用启动时初始化数据库"""
    init_db()


@app.get("/")
def root():
    return {
        "app": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# 路由挂载（后续 ticket 添加）
# from app.routers import upload, reconciliation, corrections, history
# app.include_router(upload.router, prefix="/api")
# app.include_router(reconciliation.router, prefix="/api")
# app.include_router(corrections.router, prefix="/api")
# app.include_router(history.router, prefix="/api")
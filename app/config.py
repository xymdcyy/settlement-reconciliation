# 结算对账平台配置

from pathlib import Path
from typing import Optional


class Settings:
    """应用配置"""

    # 数据库
    # 开发环境使用 SQLite，生产环境通过环境变量 DATABASE_URL 切换 PostgreSQL
    DATABASE_URL: str = "sqlite:///./settlement_reconciliation.db"
    # 例如 PostgreSQL: "postgresql://user:password@host:5432/dbname"

    # 上传文件存储目录
    UPLOAD_DIR: str = str(Path(__file__).resolve().parent.parent / "uploads")

    # CORS 允许的前端地址
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite 开发服务器
        "http://localhost:8000",
    ]

    # 应用信息
    APP_TITLE: str = "结算对账平台 API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "我方签收记录与客户方结算单的自动核对"


settings = Settings()
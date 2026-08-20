# 结算对账平台配置

import os
from pathlib import Path
from typing import Optional


class Settings:
    """应用配置

    关键项支持通过环境变量覆盖，便于在不同环境（开发 SQLite / 生产 PostgreSQL）
    和隔离测试之间切换，而无需改动代码。
    """

    # 数据库
    # 开发环境默认使用 SQLite，生产环境通过环境变量 DATABASE_URL 切换 PostgreSQL
    # 例如 PostgreSQL: "postgresql://user:password@host:5432/dbname"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./settlement_reconciliation.db")

    # 上传文件存储目录（可通过环境变量 UPLOAD_DIR 覆盖）
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads")
    )

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
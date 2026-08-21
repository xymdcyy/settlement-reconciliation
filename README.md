# 结算对账中心

> 基于 v2.0 架构的结算对账管理平台

## 快速开始

### 后端

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
uv sync

# 运行开发服务器
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

访问 http://localhost:5173

## 架构文档

完整的架构文档在 [docs/architecture/](docs/architecture/) 目录下：

- [业务模型](docs/architecture/01-business-model.md)
- [数据模型](docs/architecture/02-data-model.md)
- [系统设计](docs/architecture/03-system-design.md)
- [迁移计划](docs/architecture/04-migration-plan.md)
- [关键决策](docs/architecture/05-decisions.md)

## 项目结构

```
├── app/                    # 后端应用
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 配置
│   ├── database.py        # 数据库连接
│   ├── models/            # SQLAlchemy 模型
│   ├── schemas/           # Pydantic 模型
│   ├── routers/           # API 路由
│   ├── services/          # 业务逻辑
│   ├── engines/           # 匹配引擎（插件化）
│   └── utils/             # 工具函数
│
├── frontend/              # 前端应用
│   ├── src/
│   │   ├── views/         # 页面
│   │   ├── components/    # 组件
│   │   ├── router/        # 路由
│   │   └── api/           # API 调用
│   └── ...
│
├── scripts/               # 工具脚本
│   ├── migration/         # 数据迁移工具
│   └── gh-push.py         # Git 推送工具
│
├── tests/                 # 测试
│
└── docs/                  # 文档
    ├── architecture/      # v2.0 架构文档
    └── archive/           # v1.0 归档文档
```

## 核心功能

- **台账管理**：200 客户的签收-开票台账集中管理
- **对账核对**：50-80 客户的自动匹配 + 人工核对（插件化引擎）
- **开票管理**：可开票清单、生成开票清单、导入已开票清单
- **红冲工具**：自动查找蓝票、生成确认单、回录红通号
- **未决池**：跨月差异的滚动管理和可视化

## 技术栈

- **后端**：FastAPI + SQLAlchemy + PostgreSQL/SQLite
- **前端**：Vue 3 + Element Plus + Vite
- **引擎**：插件化 Python 类（天猫/重百/...）

## 开发指南

### 本地环境

- **Python**：必须使用 `.venv/Scripts/python.exe` 或 `uv run`（裸 `python` 是坏的）
- **Git 推送**：使用 `scripts/gh-push.py`（`git push` 被防火墙拦截）

### 添加新客户

1. 在系统管理页面新建客户
2. 如果有对账单，配置引擎
3. 运行迁移工具导入历史台账

### 添加新引擎

1. 在 `app/engines/` 下创建客户目录
2. 继承 `MatchEngine` 实现接口
3. 在 `app/engines/__init__.py` 注册

详见 [docs/architecture/03-system-design.md](docs/architecture/03-system-design.md)

## License

内部项目，不对外开放

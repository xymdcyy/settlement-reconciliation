# 引擎注册表

import importlib
from typing import Optional

from app.engines.base import MatchEngine

# 引擎注册表：customer_id → (模块路径, 类名)
_ENGINE_REGISTRY: dict[int, tuple[str, str]] = {
    1: ("app.engines.tmall.engine", "TmallEngine"),  # 天猫优品经销
    # 2: ("app.engines.chongbai.engine", "ChongbaiEngine"),
}


def get_engine(customer_id: int) -> Optional[MatchEngine]:
    """根据客户ID获取引擎实例"""
    if customer_id not in _ENGINE_REGISTRY:
        return None

    module_path, class_name = _ENGINE_REGISTRY[customer_id]
    module = importlib.import_module(module_path)
    engine_class = getattr(module, class_name)
    return engine_class()


def register_engine(customer_id: int, module_path: str, class_name: str):
    """注册新引擎（新增客户时调用）"""
    _ENGINE_REGISTRY[customer_id] = (module_path, class_name)


def list_registered_engines() -> dict[int, str]:
    """列出所有已注册的引擎"""
    return {cid: info[1] for cid, info in _ENGINE_REGISTRY.items()}
# 测试：引擎注册表

import pytest
from app.engines import get_engine, register_engine, list_registered_engines
from app.engines.base import MatchEngine


def test_register_and_get_engine():
    """注册引擎后可以获取实例"""
    # 注册模板引擎
    register_engine(999, "app.engines.template.engine", "TemplateEngine")

    engine = get_engine(999)
    assert engine is not None
    assert isinstance(engine, MatchEngine)
    assert engine.engine_name == "TemplateEngine"

    # 清理
    from app.engines import _ENGINE_REGISTRY
    del _ENGINE_REGISTRY[999]


def test_get_engine_nonexistent():
    """获取不存在的引擎返回 None"""
    engine = get_engine(99999)
    assert engine is None


def test_list_registered_engines():
    """列出已注册引擎"""
    register_engine(998, "app.engines.template.engine", "TemplateEngine")
    engines = list_registered_engines()
    assert 998 in engines
    assert engines[998] == "TemplateEngine"

    from app.engines import _ENGINE_REGISTRY
    del _ENGINE_REGISTRY[998]


def test_engine_has_abstract_methods():
    """引擎实例有抽象方法"""
    register_engine(997, "app.engines.template.engine", "TemplateEngine")
    engine = get_engine(997)
    assert engine is not None

    # 有 parse_customer_data 和 match 方法
    assert hasattr(engine, "parse_customer_data")
    assert hasattr(engine, "match")

    # 有属性
    assert engine.engine_name == "TemplateEngine"
    assert engine.engine_version == "v0.1.0"

    from app.engines import _ENGINE_REGISTRY
    del _ENGINE_REGISTRY[997]
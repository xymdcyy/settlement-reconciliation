# 数据库种子数据脚本

"""为数据库插入初始种子数据（客户、引擎配置等）"""

from app.database import SessionLocal, init_db
from app.models.models import Customer, EngineConfig


def seed():
    init_db()
    db = SessionLocal()

    try:
        # 检查是否已有数据
        if db.query(Customer).count() > 0:
            print("数据库已有数据，跳过种子插入")
            return

        # 创建默认客户：天猫优品经销
        tmall = Customer(
            name="天猫优品经销",
            slug="tmall",
            description="天猫优品经销客户，使用 TmallEngine 匹配引擎",
            is_active=True,
            # 我方明细的“结算客户名称”为分公司法人全称
            # （如“张家口天猫优品电子商务有限公司-经销”），
            # 需同时包含以下全部关键词才归属本客户
            match_keywords=["天猫优品", "经销"],
        )
        db.add(tmall)
        db.flush()

        # 创建引擎配置
        engine_config = EngineConfig(
            customer_id=tmall.id,
            engine_name="tmall",
            engine_version="v1.0.0",
            config_params={
                "exact_confidence": 1.0,
                "loose_confidence": 0.8,
            },
            is_active=True,
        )
        db.add(engine_config)

        db.commit()
        print(f"种子数据已创建:")
        print(f"  - 客户: {tmall.name} (id={tmall.id})")
        print(f"  - 引擎配置: {engine_config.engine_name} v{engine_config.engine_version}")

    except Exception as e:
        db.rollback()
        print(f"种子数据创建失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
# 客户 API 路由（Phase 2：客户管理 CRUD + 引擎绑定）

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines import get_engine_by_name, list_available_engines
from app.models.models import Customer, EngineConfig
from app.schemas import (
    CustomerCreate,
    CustomerDetailResponse,
    CustomerResponse,
    CustomerUpdate,
    EngineConfigPayload,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _get_or_404(db: Session, customer_id: int) -> Customer:
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"客户 {customer_id} 不存在")
    return c


def _check_slug_free(db: Session, slug: str, exclude_id: int = None):
    q = db.query(Customer).filter(Customer.slug == slug)
    if exclude_id is not None:
        q = q.filter(Customer.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409, detail=f"客户标识 slug '{slug}' 已被占用")


@router.get("/engines", response_model=list[str])
def list_engines():
    """可绑定的匹配引擎列表（供客户管理界面下拉选择）。"""
    return list_available_engines()


@router.get("", response_model=list[CustomerDetailResponse])
def list_customers(include_inactive: bool = True, db: Session = Depends(get_db)):
    """客户列表（含引擎绑定配置）。默认返回全部（含停用）。"""
    q = db.query(Customer)
    if not include_inactive:
        q = q.filter(Customer.is_active == True)
    return q.order_by(Customer.id).all()


@router.post("", response_model=CustomerDetailResponse, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """新建客户（可同时携带引擎绑定）。"""
    _check_slug_free(db, payload.slug)
    c = Customer(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        is_active=payload.is_active,
        match_keywords=payload.match_keywords,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{customer_id}", response_model=CustomerDetailResponse)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)):
    """更新客户基本信息。"""
    c = _get_or_404(db, customer_id)
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data:
        _check_slug_free(db, data["slug"], exclude_id=customer_id)
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """删除客户（软删除：置为停用，保留对账历史）。"""
    c = _get_or_404(db, customer_id)
    c.is_active = False
    db.commit()
    return {"success": True, "message": f"客户 '{c.name}' 已停用", "id": customer_id}


@router.put("/{customer_id}/engine", response_model=CustomerDetailResponse)
def bind_engine(customer_id: int, payload: EngineConfigPayload, db: Session = Depends(get_db)):
    """绑定/更新客户的匹配引擎配置。"""
    c = _get_or_404(db, customer_id)
    # 校验引擎名可用，并登记到运行时注册表
    if get_engine_by_name(payload.engine_name) is None:
        raise HTTPException(status_code=400, detail=f"未知引擎 '{payload.engine_name}'，可选: {list_available_engines()}")
    from app.engines import AVAILABLE_ENGINES, register_engine
    register_engine(customer_id, *AVAILABLE_ENGINES[payload.engine_name])
    ec = db.query(EngineConfig).filter(EngineConfig.customer_id == customer_id).first()
    if ec:
        ec.engine_name = payload.engine_name
        ec.engine_version = payload.engine_version
        ec.config_params = payload.config_params
        ec.is_active = payload.is_active
    else:
        ec = EngineConfig(
            customer_id=customer_id,
            engine_name=payload.engine_name,
            engine_version=payload.engine_version,
            config_params=payload.config_params,
            is_active=payload.is_active,
        )
        db.add(ec)
    db.commit()
    db.refresh(c)
    return c

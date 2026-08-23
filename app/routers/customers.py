# 客户 API 路由

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines import get_engine_by_name, list_available_engines
from app.models import Customer
from app.schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
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


@router.get("", response_model=list[CustomerResponse])
def list_customers(include_inactive: bool = True, db: Session = Depends(get_db)):
    """客户列表。默认返回全部（含停用）。"""
    q = db.query(Customer)
    if not include_inactive:
        q = q.filter(Customer.is_active == True)
    return q.order_by(Customer.id).all()


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """获取单个客户详情。"""
    return _get_or_404(db, customer_id)


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """新建客户。"""
    _check_slug_free(db, payload.slug)
    c = Customer(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        has_statement=payload.has_statement,
        engine_name=payload.engine_name,
        extra_fields_config=payload.extra_fields_config,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{customer_id}", response_model=CustomerResponse)
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

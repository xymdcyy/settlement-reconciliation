# 客户 API 路由

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Customer
from app.schemas import CustomerResponse

router = APIRouter(prefix="/api", tags=["customers"])


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(db: Session = Depends(get_db)):
    """获取所有激活的客户列表"""
    customers = db.query(Customer).filter(Customer.is_active == True).all()
    return customers
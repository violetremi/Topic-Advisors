"""企业 CRUD 路由（按用户隔离）"""
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user, get_owned_company
from models import Company, User
from schemas import CompanyCreate, CompanyOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies", tags=["企业"])


def _generate_company_code() -> str:
    """生成企业编号：QY + 年月日 + - + 4位序号"""
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    seq = now.microsecond % 10000  # 简单实现，生产环境建议用数据库序列
    return f"QY{date_part}-{seq:04d}"


@router.get("", response_model=List[CompanyOut])
async def list_companies(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """企业列表（分页，仅当前用户）"""
    stmt = (
        select(Company)
        .where(Company.user_id == current_user.id)
        .order_by(Company.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    companies = result.scalars().all()
    return companies


@router.get("/count")
async def count_companies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """企业总数（仅当前用户）"""
    result = await db.execute(
        select(func.count(Company.id)).where(Company.user_id == current_user.id)
    )
    total = result.scalar()
    return {"total": total}


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个企业（校验归属）"""
    company = await get_owned_company(company_id, current_user, db)
    return company


@router.post("", response_model=CompanyOut, status_code=201)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增企业（归属当前用户）"""
    # 检查信用代码是否已存在（同一用户范围内）
    result = await db.execute(
        select(Company).where(
            Company.credit_code == data.credit_code,
            Company.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该统一社会信用代码已存在")

    company = Company(
        company_code=_generate_company_code(),
        name=data.name,
        credit_code=data.credit_code,
        user_id=current_user.id,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    logger.info(f"新增企业: {company.name} ({company.company_code}) 用户={current_user.username}")
    return company

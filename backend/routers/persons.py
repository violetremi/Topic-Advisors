"""人员 CRUD 路由（按用户隔离）"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user, get_owned_company
from models import Person, User
from schemas import PersonCreate, PersonUpdate, PersonOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies/{company_id}/persons", tags=["人员"])


@router.get("", response_model=List[PersonOut])
async def list_persons(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(Person).where(Person.company_id == company_id).order_by(Person.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=PersonOut, status_code=201)
async def create_person(
    company_id: int,
    data: PersonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_owned_company(company_id, current_user, db)
    person = Person(
        company_id=company_id,
        name=data.name,
        position=data.position,
        joined_date=data.joined_date or "",
        background=data.background or "",
        public_links=data.public_links or "",
        notes=data.notes or "",
        hobbies=data.hobbies or "",
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    logger.info(f"新增人员: {person.name} ({person.position}) 企业ID={company_id} 用户={current_user.username}")
    return person


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.company_id == company_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")
    return person


@router.put("/{person_id}", response_model=PersonOut)
async def update_person(
    company_id: int,
    person_id: int,
    data: PersonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.company_id == company_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(person, field, value)
    await db.commit()
    await db.refresh(person)
    return person


@router.delete("/{person_id}")
async def delete_person(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.company_id == company_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")
    await db.delete(person)
    await db.commit()
    return {"message": "删除成功"}

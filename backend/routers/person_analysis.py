"""人员话题分析路由 - 生成和查看个人话题分析（按用户隔离）"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import (
    get_current_user,
    get_owned_company,
    get_user_llm_config,
    llm_config_kwargs,
)
from models import Company, Person, PersonAnalysis, User
from schemas import TopicAnalysisOut
from services.agent_service import run_topic_analysis, call_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies/{company_id}/persons", tags=["人员分析"])


def _strip_think_tags(text: str) -> str:
    import re
    return re.sub(r'<think>[\s\S]*?</think>', '', text).strip()


@router.get("/{person_id}/topic-analysis")
async def get_topic_analysis(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取人员的最新话题分析"""
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(PersonAnalysis)
        .where(
            PersonAnalysis.company_id == company_id,
            PersonAnalysis.person_id == person_id,
        )
        .order_by(desc(PersonAnalysis.created_at))
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        return {"id": None, "person_id": person_id, "content": "", "created_at": None}
    return {
        "id": analysis.id,
        "person_id": analysis.person_id,
        "content": analysis.content,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


@router.post("/{person_id}/topic-analysis")
async def create_topic_analysis(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成人员话题分析"""
    company = await get_owned_company(company_id, current_user, db)

    person = await db.get(Person, person_id)
    if not person or person.company_id != company_id:
        raise HTTPException(status_code=404, detail="人员不存在")

    cfg = await get_user_llm_config(current_user, db)
    from services.vector_store import fetch_stored_news_for_analysis

    stored_news = await fetch_stored_news_for_analysis(
        db,
        company_id,
        company.name,
        base_url=cfg["base_url"],
        api_key=cfg.get("api_key") or "",
        model=cfg.get("embed_model") or "text-embedding-bge-m3",
        top_k=16,
        person_id=person_id,
    )

    person_data = {
        "name": person.name,
        "position": person.position,
        "joined_date": person.joined_date,
        "background": person.background,
        "public_links": person.public_links,
        "notes": person.notes,
        "hobbies": person.hobbies,
    }

    logger.info(f"开始生成话题分析: {person.name}, 用户={current_user.username}, 模型={cfg['model']}")
    content = await run_topic_analysis(
        company.name,
        person_data,
        stored_news=stored_news,
        **llm_config_kwargs(cfg),
    )

    if content.startswith("（"):
        logger.warning(f"话题分析 LLM 返回错误: {content[:100]}")
        raise HTTPException(status_code=502, detail=content)

    analysis = PersonAnalysis(
        company_id=company_id,
        person_id=person_id,
        content=content,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    logger.info(f"话题分析完成: analysis_id={analysis.id}")
    return {
        "id": analysis.id,
        "person_id": analysis.person_id,
        "content": analysis.content,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }

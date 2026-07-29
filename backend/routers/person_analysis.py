"""人员话题分析路由 - 生成和查看个人话题分析"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Company, Person, PersonAnalysis, SystemConfig, Report
from schemas import TopicAnalysisOut
from services.agent_service import run_topic_analysis, call_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies/{company_id}/persons", tags=["人员分析"])


async def _load_llm_config(db: AsyncSession) -> dict:
    """从 SystemConfig 表加载运行时 LLM 配置"""
    from config.settings import settings

    result = await db.execute(select(SystemConfig))
    rows = result.scalars().all()
    cfg = {r.key: r.value for r in rows}
    return {
        "base_url": cfg.get("llm_base_url") or settings.openai_base_url,
        "api_key": cfg.get("llm_api_key") or settings.openai_api_key,
        "model": cfg.get("llm_model") or settings.llm_model,
        "embed_model": cfg.get("llm_embed_model") or settings.embed_model,
    }


def _llm_config_kwargs(cfg: dict) -> dict:
    return {
        "base_url_override": cfg["base_url"],
        "api_key_override": cfg["api_key"],
        "model_override": cfg["model"],
    }


def _strip_think_tags(text: str) -> str:
    import re
    return re.sub(r'<think>[\s\S]*?</think>', '', text).strip()


@router.get("/{person_id}/topic-analysis")
async def get_topic_analysis(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取人员的最新话题分析"""
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
):
    """生成人员话题分析"""
    # 检查企业和人员是否存在
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    person = await db.get(Person, person_id)
    if not person or person.company_id != company_id:
        raise HTTPException(status_code=404, detail="人员不存在")

    cfg = await _load_llm_config(db)
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

    logger.info(f"开始生成话题分析: {person.name}, 模型={cfg['model']}")
    content = await run_topic_analysis(
        company.name,
        person_data,
        stored_news=stored_news,
        **_llm_config_kwargs(cfg),
    )

    if content.startswith("（"):
        logger.warning(f"话题分析 LLM 返回错误: {content[:100]}")
        raise HTTPException(status_code=502, detail=content)

    # 保存分析结果
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

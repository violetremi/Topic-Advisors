"""话题链路由 - 综合分析生成话题链（按用户隔离）"""
import logging
from typing import List

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
from models import Company, Person, PersonAnalysis, Report, TopicChain, User
from schemas import TopicChainRequest, TopicChainOut
from services.agent_service import run_topic_chain, call_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies/{company_id}/topic-chain", tags=["话题链"])


def _strip_think_tags(text: str) -> str:
    import re
    return re.sub(r'<think>[\s\S]*?</think>', '', text).strip()


async def _get_latest_report(
    db: AsyncSession, company_id: int, report_type: str
) -> Report | None:
    from sqlalchemy import desc as _desc
    result = await db.execute(
        select(Report)
        .where(Report.company_id == company_id, Report.report_type == report_type)
        .order_by(_desc(Report.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("")
async def list_topic_chains(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取该企业的所有话题链"""
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(TopicChain)
        .where(TopicChain.company_id == company_id)
        .order_by(desc(TopicChain.created_at))
    )
    chains = result.scalars().all()
    return [
        {
            "id": c.id,
            "company_id": c.company_id,
            "content": c.content,
            "person_ids": [int(x) for x in c.person_ids.split(",") if x.strip().isdigit()] if c.person_ids else [],
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chains
    ]


@router.get("/latest")
async def get_latest_topic_chain(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最新的话题链"""
    await get_owned_company(company_id, current_user, db)
    result = await db.execute(
        select(TopicChain)
        .where(TopicChain.company_id == company_id)
        .order_by(desc(TopicChain.created_at))
        .limit(1)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        return {"id": None, "company_id": company_id, "content": "", "person_ids": [], "created_at": None}
    return {
        "id": chain.id,
        "company_id": chain.company_id,
        "content": chain.content,
        "person_ids": [int(x) for x in chain.person_ids.split(",") if x.strip().isdigit()] if chain.person_ids else [],
        "created_at": chain.created_at.isoformat() if chain.created_at else None,
    }


@router.post("")
async def create_topic_chain(
    company_id: int,
    req: TopicChainRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """综合研判：结合行业/企业报告、向量化新闻与所选人员关联新闻，生成拜访沟通策略与话题链。"""
    company = await get_owned_company(company_id, current_user, db)

    latest_industry = await _get_latest_report(db, company_id, "industry")
    latest_company = await _get_latest_report(db, company_id, "company")

    missing = []
    if not latest_industry:
        missing.append("行业分析")
    if not latest_company:
        missing.append("企业分析")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"请先完成以下分析: {'、'.join(missing)}",
        )

    person_analyses_data = []
    for pid in req.person_ids:
        person = await db.get(Person, pid)
        if not person or person.company_id != company_id:
            continue

        analysis_result = await db.execute(
            select(PersonAnalysis)
            .where(
                PersonAnalysis.company_id == company_id,
                PersonAnalysis.person_id == pid,
            )
            .order_by(desc(PersonAnalysis.created_at))
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()

        person_analyses_data.append({
            "name": person.name,
            "position": person.position,
            "hobbies": person.hobbies,
            "topic_analysis": analysis.content if analysis else "（暂无话题分析）",
        })

    if not person_analyses_data:
        raise HTTPException(status_code=400, detail="请至少选择一名有效人员")

    cfg = await get_user_llm_config(current_user, db)
    logger.info(
        f"开始综合研判话题链: {company.name}, 用户={current_user.username}, 人员={len(person_analyses_data)}, "
        f"person_ids={req.person_ids}, 模型={cfg['model']}"
    )

    from services.vector_store import fetch_stored_news_for_analysis

    stored_news = await fetch_stored_news_for_analysis(
        db,
        company_id,
        company.name,
        base_url=cfg["base_url"],
        api_key=cfg.get("api_key") or "",
        model=cfg.get("embed_model") or "text-embedding-bge-m3",
        top_k=20,
        person_ids=list(req.person_ids),
    )

    # 截短过长的报告/新闻，避免推理模型 token 耗尽
    def _truncate(text: str, max_len: int = 800) -> str:
        if not text or len(text) <= max_len:
            return text
        return text[:max_len] + "\n\n…（后续内容已截断，以上为关键信息）"

    content = await run_topic_chain(
        company_name=company.name,
        industry_report=_truncate(latest_industry.content, 600),
        company_report=_truncate(latest_company.content, 600),
        person_analyses=[{
            "name": p["name"],
            "position": p["position"],
            "hobbies": p["hobbies"],
            "topic_analysis": _truncate(p.get("topic_analysis", ""), 400),
        } for p in person_analyses_data],
        stored_news=_truncate(stored_news, 1200),
        **llm_config_kwargs(cfg),
    )

    if content.startswith("（"):
        logger.warning(f"话题链 LLM 返回错误: {content[:100]}")
        raise HTTPException(status_code=502, detail=content)

    person_ids_str = ",".join(str(pid) for pid in req.person_ids)
    chain = TopicChain(
        company_id=company_id,
        content=content,
        person_ids=person_ids_str,
    )
    db.add(chain)
    await db.commit()
    await db.refresh(chain)

    logger.info(f"话题链生成完成: chain_id={chain.id}")
    return {
        "id": chain.id,
        "company_id": chain.company_id,
        "content": chain.content,
        "person_ids": req.person_ids,
        "created_at": chain.created_at.isoformat() if chain.created_at else None,
    }

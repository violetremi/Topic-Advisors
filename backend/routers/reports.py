"""报告路由 - 触发 Agent 分析并查看历史报告"""
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Company, Person, Report, CheckRun, SystemConfig
from schemas import ReportOut, CheckRunOut, CheckRunListItem
from services.agent_service import (
    run_industry_analysis,
    run_company_analysis,
    run_people_analysis,
    run_summary_analysis,
    call_llm,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies/{company_id}/reports", tags=["报告"])


# ── 运行时配置加载 ──

async def _load_llm_config(db: AsyncSession) -> dict:
    """从 SystemConfig 表加载运行时 LLM 配置，空值回退到 .env 中的值"""
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
    """将 LLM 配置转为 call_llm 的 override 参数"""
    return {
        "base_url_override": cfg["base_url"],
        "api_key_override": cfg["api_key"],
        "model_override": cfg["model"],
    }


# ── 辅助函数 ──

def _strip_think_tags(text: str) -> str:
    """移除模型推理标签 <think>...</think>"""
    import re
    return re.sub(r'<think>[\s\S]*?</think>', '', text).strip()


async def _save_report(db: AsyncSession, company_id: int, report_type: str, content: str, batch_id: str | None = None) -> Report:
    """保存报告，清理 think 标签并提取前 100 字摘要"""
    clean = _strip_think_tags(content)
    plain_text = clean.replace("#", "").replace("*", "").replace("\n", " ").strip()
    summary = plain_text[:100]
    report = Report(
        company_id=company_id,
        report_type=report_type,
        content=content,
        summary=summary,
        batch_id=batch_id,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def _get_latest_report(
    db: AsyncSession, company_id: int, report_type: str
) -> Report | None:
    """获取某企业某类型的最新一份报告"""
    result = await db.execute(
        select(Report)
        .where(Report.company_id == company_id, Report.report_type == report_type)
        .order_by(desc(Report.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _report_response(report: Report) -> dict:
    return {
        "id": report.id,
        "report_type": report.report_type,
        "content": report.content,
        "summary": report.summary,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


# ── 核查批次历史（必须放在 /{report_type} 之前，避免路由冲突）──

@router.get("/check-runs", response_model=List[CheckRunListItem])
async def list_check_runs(company_id: int, db: AsyncSession = Depends(get_db)):
    """列出某企业的所有全量分析核查批次（倒序）"""
    result = await db.execute(
        select(CheckRun)
        .where(CheckRun.company_id == company_id)
        .order_by(desc(CheckRun.created_at))
    )
    return result.scalars().all()


@router.get("/check-runs/{run_id}")
async def get_check_run(company_id: int, run_id: int, db: AsyncSession = Depends(get_db)):
    """获取某批次的完整信息（含 4 份报告）"""
    check_run = await db.get(CheckRun, run_id)
    if not check_run or check_run.company_id != company_id:
        raise HTTPException(status_code=404, detail="核查批次不存在")

    # 查询该批次的所有报告
    rr = await db.execute(
        select(Report)
        .where(Report.company_id == company_id, Report.batch_id == check_run.batch_id)
        .order_by(Report.created_at)
    )
    reports = rr.scalars().all()

    return {
        "id": check_run.id,
        "company_id": check_run.company_id,
        "status": check_run.status,
        "summary_text": check_run.summary_text,
        "created_at": check_run.created_at.isoformat() if check_run.created_at else None,
        "reports": [_report_response(r) for r in reports],
    }


# ── 获取历史报告列表 ──

@router.get("", response_model=List[ReportOut])
async def list_reports(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Report)
        .where(Report.company_id == company_id)
        .order_by(desc(Report.created_at))
    )
    return result.scalars().all()


@router.get("/{report_type}", response_model=List[ReportOut])
async def list_reports_by_type(
    company_id: int, report_type: str, db: AsyncSession = Depends(get_db)):
    """按类型获取报告列表"""
    valid_types = {"industry", "company", "people", "summary"}
    if report_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效的报告类型: {report_type}")
    result = await db.execute(
        select(Report)
        .where(Report.company_id == company_id, Report.report_type == report_type)
        .order_by(desc(Report.created_at))
    )
    return result.scalars().all()


# ── 触发行业分析 ──

@router.post("/industry")
async def trigger_industry_analysis(company_id: int, db: AsyncSession = Depends(get_db)):
    """触发行业分析 Agent"""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    cfg = await _load_llm_config(db)
    logger.info(f"开始行业分析: {company.name}, 模型={cfg['model']}")
    content = await run_industry_analysis(
        company.name, company.credit_code, **_llm_config_kwargs(cfg)
    )

    # 检查 LLM 是否返回了错误信息，如果是则直接透传错误
    if content.startswith("（"):
        logger.warning(f"行业分析 LLM 返回错误: {content[:100]}")
        # 不保存错误内容为报告，直接返回错误
        raise HTTPException(status_code=502, detail=content)

    report = await _save_report(db, company_id, "industry", content)
    logger.info(f"行业分析完成: report_id={report.id}")
    return _report_response(report)


# ── 触发企业分析 ──

@router.post("/company")
async def trigger_company_analysis(company_id: int, db: AsyncSession = Depends(get_db)):
    """触发企业分析 Agent"""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    cfg = await _load_llm_config(db)
    logger.info(f"开始企业分析: {company.name}, 模型={cfg['model']}")
    content = await run_company_analysis(
        company.name, company.credit_code, **_llm_config_kwargs(cfg)
    )

    if content.startswith("（"):
        logger.warning(f"企业分析 LLM 返回错误: {content[:100]}")
        raise HTTPException(status_code=502, detail=content)

    report = await _save_report(db, company_id, "company", content)
    logger.info(f"企业分析完成: report_id={report.id}")
    return _report_response(report)


# ── 触发人员分析 ──

@router.post("/people")
async def trigger_people_analysis(company_id: int, db: AsyncSession = Depends(get_db)):
    """触发人员分析 Agent"""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    # 检查是否有人员
    result = await db.execute(
        select(Person).where(Person.company_id == company_id)
    )
    people = result.scalars().all()
    if not people:
        raise HTTPException(status_code=400, detail="请先添加至少一名核心人员")

    cfg = await _load_llm_config(db)
    logger.info(f"开始人员分析: {company.name}, 人数={len(people)}, 模型={cfg['model']}")
    people_data = [
        {
            "name": p.name,
            "position": p.position,
            "joined_date": p.joined_date,
            "background": p.background,
            "public_links": p.public_links,
            "notes": p.notes,
            "hobbies": p.hobbies,
        }
        for p in people
    ]
    content = await run_people_analysis(company.name, people_data, **_llm_config_kwargs(cfg))

    if content.startswith("（"):
        logger.warning(f"人员分析 LLM 返回错误: {content[:100]}")
        raise HTTPException(status_code=502, detail=content)

    report = await _save_report(db, company_id, "people", content)
    logger.info(f"人员分析完成: report_id={report.id}")
    return _report_response(report)


# ── 触发综合研判 ──

@router.post("/summary")
async def trigger_summary_analysis(company_id: int, db: AsyncSession = Depends(get_db)):
    """触发综合研判 Agent（需要三份报告齐全）"""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    industry_report = await _get_latest_report(db, company_id, "industry")
    company_report = await _get_latest_report(db, company_id, "company")
    people_report = await _get_latest_report(db, company_id, "people")

    missing = []
    if not industry_report:
        missing.append("行业分析")
    if not company_report:
        missing.append("企业分析")
    if not people_report:
        missing.append("人员分析")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"请先完成以下分析: {'、'.join(missing)}",
        )

    cfg = await _load_llm_config(db)
    logger.info(f"开始综合研判: {company.name}, 模型={cfg['model']}")

    # 查询人员列表
    people_result = await db.execute(
        select(Person).where(Person.company_id == company_id)
    )
    people = people_result.scalars().all()
    people_data = [
        {
            "name": p.name,
            "position": p.position,
            "joined_date": p.joined_date,
            "background": p.background,
            "public_links": p.public_links,
            "notes": p.notes,
            "hobbies": p.hobbies,
        }
        for p in people
    ]

    from services.vector_store import fetch_stored_news_for_analysis

    stored_news = await fetch_stored_news_for_analysis(
        db,
        company_id,
        company.name,
        base_url=cfg["base_url"],
        api_key=cfg.get("api_key") or "",
        model=cfg.get("embed_model") or "text-embedding-bge-m3",
    )

    content = await run_summary_analysis(
        company_name=company.name,
        industry_report=industry_report.content,
        company_report=company_report.content,
        people_report=people_report.content,
        people_list=people_data,
        stored_news=stored_news,
        **_llm_config_kwargs(cfg),
    )

    if content.startswith("（"):
        logger.warning(f"综合研判 LLM 返回错误: {content[:100]}")
        raise HTTPException(status_code=502, detail=content)

    report = await _save_report(db, company_id, "summary", content)
    logger.info(f"综合研判完成: report_id={report.id}")
    return _report_response(report)


# ── 一键全量顺序分析（含批次管理）──

@router.post("/full-analysis")
async def trigger_full_analysis(company_id: int, db: AsyncSession = Depends(get_db)):
    """一键全量分析：依次执行行业→企业→人员→综合研判，作为同一批次入库"""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    people_result = await db.execute(
        select(Person).where(Person.company_id == company_id)
    )
    people = people_result.scalars().all()
    if not people:
        raise HTTPException(status_code=400, detail="请先添加至少一名核心人员")

    cfg = await _load_llm_config(db)
    batch_id = str(uuid.uuid4())
    result = {}

    # 创建核查批次记录
    check_run = CheckRun(company_id=company_id, batch_id=batch_id, status="running", summary_text="")
    db.add(check_run)
    await db.commit()
    await db.refresh(check_run)

    try:
        # Step 1: 行业分析
        logger.info(f"[全量分析/1] 开始行业分析: {company.name}")
        industry_content = await run_industry_analysis(
            company.name, company.credit_code, **_llm_config_kwargs(cfg)
        )
        if industry_content.startswith("（"):
            raise RuntimeError(f"行业分析失败: {industry_content[:100]}")
        industry_report = await _save_report(db, company_id, "industry", industry_content, batch_id)
        result["industry"] = _report_response(industry_report)
        logger.info(f"[全量分析/1] 行业分析完成")

        # Step 2: 企业分析
        logger.info(f"[全量分析/2] 开始企业分析: {company.name}")
        company_content = await run_company_analysis(
            company.name, company.credit_code, **_llm_config_kwargs(cfg)
        )
        if company_content.startswith("（"):
            raise RuntimeError(f"企业分析失败: {company_content[:100]}")
        company_report = await _save_report(db, company_id, "company", company_content, batch_id)
        result["company"] = _report_response(company_report)
        logger.info(f"[全量分析/2] 企业分析完成")

        # Step 3: 人员分析
        logger.info(f"[全量分析/3] 开始人员分析: {company.name}, 人数={len(people)}")
        people_data = [
            {"name": p.name, "position": p.position, "joined_date": p.joined_date,
             "background": p.background, "public_links": p.public_links,
             "notes": p.notes, "hobbies": p.hobbies} for p in people
        ]
        people_content = await run_people_analysis(company.name, people_data, **_llm_config_kwargs(cfg))
        if people_content.startswith("（"):
            raise RuntimeError(f"人员分析失败: {people_content[:100]}")
        people_report = await _save_report(db, company_id, "people", people_content, batch_id)
        result["people"] = _report_response(people_report)
        logger.info(f"[全量分析/3] 人员分析完成")

        # Step 4: 综合研判（结合向量检索的入库新闻）
        logger.info(f"[全量分析/4] 开始综合研判: {company.name}")
        from services.vector_store import fetch_stored_news_for_analysis

        stored_news = await fetch_stored_news_for_analysis(
            db,
            company_id,
            company.name,
            base_url=cfg["base_url"],
            api_key=cfg.get("api_key") or "",
            model=cfg.get("embed_model") or "text-embedding-bge-m3",
        )
        summary_content = await run_summary_analysis(
            company_name=company.name,
            industry_report=industry_content,
            company_report=company_content,
            people_report=people_content,
            people_list=people_data,
            stored_news=stored_news,
            **_llm_config_kwargs(cfg),
        )
        if summary_content.startswith("（"):
            raise RuntimeError(f"综合研判失败: {summary_content[:100]}")
        summary_report = await _save_report(db, company_id, "summary", summary_content, batch_id)
        result["summary"] = _report_response(summary_report)

        # 更新批次状态
        summary_clean = _strip_think_tags(summary_content)
        check_run.status = "completed"
        check_run.summary_text = summary_clean[:200].replace("#", "").replace("*", "").replace("\n", " ").strip()
        await db.commit()

        logger.info(f"[全量分析/4] 综合研判完成，批次={batch_id}")
    except Exception as e:
        check_run.status = "failed"
        check_run.summary_text = f"分析中断: {str(e)[:200]}"
        await db.commit()
        logger.error(f"全量分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"全量分析失败: {str(e)}")

    result["check_run_id"] = check_run.id
    return result

"""新闻搜索路由 - 提供行业新闻和企业新闻（AI 过滤 + 持久化 + 向量化，按用户隔离）"""
import hashlib
import logging
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import (
    get_current_user,
    get_owned_company,
    get_user_llm_config,
    llm_config_kwargs,
)
from models import Company, News, Person, User
from schemas import NewsResponse, HobbyNewsGroup, PersonHobbyNewsResponse
from services.agent_service import (
    web_search,
    filter_news_with_ai,
    generate_hobby_search_keywords,
    generate_company_person_search_keywords,
)
from services.vector_store import vectorize_news_rows

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies/{company_id}/news", tags=["新闻"])

# 人员新闻自带的企业标签名（不可作为兴趣标签录入）
COMPANY_TAB_LABEL = "企业"


def parse_hobby_tags(hobbies: str | None) -> list[str]:
    """将兴趣爱好字段解析为标签列表（兼容旧自由文本；排除保留字「企业」）。"""
    raw = (hobbies or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                tags = [str(t).strip() for t in parsed if str(t).strip()]
                return _dedupe_tags(tags)
        except Exception:
            pass
    parts = re.split(r"[,，;；、|\s]+", raw)
    return _dedupe_tags([p.strip() for p in parts if p and p.strip()])


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t == COMPANY_TAB_LABEL:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def hobby_news_type(person_id: int, hobby: str) -> str:
    """为兴趣标签生成短且稳定的 news_type（适配 VARCHAR 长度）。"""
    digest = hashlib.md5(hobby.encode("utf-8")).hexdigest()[:10]
    return f"p{person_id}_h{digest}"


def company_person_news_type(person_id: int) -> str:
    """人员自带「企业」标签的 news_type。"""
    return f"p{person_id}_co"


def _company_exclude_keywords(company_name: str, credit_code: str = "") -> list[str]:
    """生成兴趣新闻硬排除用的企业关键词。"""
    keys: list[str] = []
    name = (company_name or "").strip()
    if name:
        keys.append(name)
        short = re.sub(
            r"(股份有限公司|有限责任公司|有限公司|集团公司|集团股份|集团)+$",
            "",
            name,
        ).strip()
        if short and short != name:
            keys.append(short)
    code = (credit_code or "").strip()
    if code:
        keys.append(code)
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if len(k) < 2:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def _drop_company_contaminated(items: list[dict], exclude_keywords: list[str]) -> list[dict]:
    """硬过滤：标题/摘要/理由中出现企业关键词的条目直接丢弃。"""
    if not exclude_keywords:
        return items
    cleaned: list[dict] = []
    for it in items:
        blob = f"{it.get('title') or ''}{it.get('snippet') or ''}{it.get('relevance_reason') or ''}"
        if any(k in blob for k in exclude_keywords):
            continue
        cleaned.append(it)
    return cleaned


async def _clear_news_type(db: AsyncSession, company_id: int, news_type: str) -> int:
    """清空某 news_type 下全部缓存（兴趣重搜时替换旧的污染数据）。"""
    result = await db.execute(
        delete(News).where(
            News.company_id == company_id,
            News.news_type == news_type,
        )
    )
    await db.commit()
    return int(result.rowcount or 0)


def _guess_industry(company_name: str) -> str:
    """通过企业名称快速猜测所属行业"""
    patterns = [
        ("科技|技术|软件|数据|智能|AI|人工|数字|云|网络|信息", "科技"),
        ("银行|保险|证券|基金|金融|支付|投资|信贷|担保", "金融"),
        ("医药|医疗|健康|生物|制药|医院|药房|康养", "医疗健康"),
        ("教育|培训|学校|学院|大学|学习|考试|留学", "教育"),
        ("汽车|出行|新能源车|自动驾驶|网约车|租车", "汽车出行"),
        ("电商|购物|零售|商城|贸易|跨境|进出口|供销", "零售电商"),
        ("物流|快递|运输|货运|配送|仓储|供应链", "物流"),
        ("地产|房产|物业|置业|建筑|工程|装修|建材|家居", "房地产"),
        ("能源|电力|光伏|风电|新能源|储能|石油|燃气", "能源"),
        ("食品|餐饮|饮料|酒|茶|乳业|农业|生鲜|零食", "消费"),
        ("制造|工业|机械|设备|化工|材料|钢铁|重工", "制造业"),
        ("通信|电信|移动|联通|卫星|基站|5G", "通信"),
        ("法律|咨询|审计|会计|税务|猎头|服务", "专业服务"),
    ]
    for pattern, industry in patterns:
        if re.search(pattern, company_name):
            return industry
    return ""


def _normalize_url(url: str) -> str:
    """规范化 URL，减少重复入库（去尾斜杠、常见追踪参数、统一小写 host）"""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        p = urlparse(raw)
        query = [
            (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith(("utm_", "spm", "from", "ref"))
        ]
        cleaned = p._replace(
            scheme=(p.scheme or "https").lower(),
            netloc=p.netloc.lower(),
            path=p.path.rstrip("/") or "/",
            query=urlencode(query),
            fragment="",
        )
        return urlunparse(cleaned)
    except Exception:
        return raw.rstrip("/").lower()


def _normalize_title(title: str) -> str:
    t = re.sub(r"\s+", "", (title or "").strip().lower())
    return t[:80]


async def _list_cached_news(
    db: AsyncSession, company_id: int, news_type: str
) -> list[News]:
    result = await db.execute(
        select(News)
        .where(News.company_id == company_id, News.news_type == news_type)
        .order_by(News.created_at.desc())
    )
    return list(result.scalars().all())


def _news_to_item(n: News) -> dict:
    return {
        "title": n.title,
        "url": n.url,
        "snippet": n.snippet or "",
        "date": n.date or "",
        "relevance_reason": n.relevance_reason or "",
    }


async def _save_news(
    db: AsyncSession, company_id: int, news_type: str, items: list[dict]
) -> list[News]:
    """将 AI 筛选新闻入库（URL / 标题去重），返回新插入的 News 行。"""
    await db.flush()

    result = await db.execute(
        select(News).where(
            News.company_id == company_id,
            News.news_type == news_type,
        )
    )
    existing_rows = list(result.scalars().all())
    existing_urls = {_normalize_url(r.url) for r in existing_rows if r.url}
    existing_titles = {_normalize_title(r.title) for r in existing_rows if r.title}

    new_rows: list[News] = []
    for item in items:
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue

        norm_url = _normalize_url(url)
        norm_title = _normalize_title(title)
        if norm_url in existing_urls:
            continue
        if norm_title and norm_title in existing_titles:
            continue

        try:
            news = News(
                company_id=company_id,
                news_type=news_type,
                title=title[:500],
                url=url[:1000],
                snippet=(item.get("snippet") or "")[:500],
                date=(item.get("date") or "")[:50],
                relevance_reason=(item.get("relevance_reason") or "")[:200],
                embedding="",
            )
            db.add(news)
            new_rows.append(news)
            existing_urls.add(norm_url)
            if norm_title:
                existing_titles.add(norm_title)
        except Exception:
            continue

    if new_rows:
        try:
            await db.commit()
            for row in new_rows:
                try:
                    await db.refresh(row)
                except Exception:
                    pass
            logger.info(
                f"新闻入库: company={company_id}, type={news_type}, "
                f"新增={len(new_rows)}/{len(items)} 条"
            )
        except Exception as e:
            logger.warning(
                f"新闻入库失败: company={company_id}, type={news_type}, err={e}"
            )
            return []

    return new_rows


async def _vectorize_saved(db: AsyncSession, rows: list[News], cfg: dict) -> None:
    if not rows:
        return
    await vectorize_news_rows(
        db,
        rows,
        base_url=cfg["base_url"],
        api_key=cfg.get("api_key") or "",
        model=cfg.get("embed_model") or "text-embedding-bge-m3",
    )


async def _search_and_filter(
    *,
    company_id: int,
    company_name: str,
    credit_code: str,
    industry_hint: str,
    news_type: str,
    queries: list[str],
    cfg: dict,
    db: AsyncSession,
    focus_topic: str = "",
    filter_mode: str = "company",
    person_name: str = "",
    person_position: str = "",
    hobbies: list[str] | None = None,
    replace_existing: bool = False,
) -> tuple[list[dict], bool, str, int]:
    """搜索 + AI 过滤 + 入库向量化。返回 (items, ai_filtered, message, 新增数)。"""
    topic = (focus_topic or "").strip()
    mode = (filter_mode or "company").strip().lower()
    exclude_keys = _company_exclude_keywords(company_name, credit_code)
    hobby_list = hobbies or []

    raw_results = []
    for q in queries:
        try:
            result = await web_search(
                q,
                max_results=6,
                search_provider=cfg.get("search_provider"),
                search_api_key=cfg.get("search_api_key"),
            )
            if result and "联网搜索暂时不可用" not in result:
                raw_results.append(f"--- 搜索: {q} ---\n{result}")
        except Exception as e:
            logger.warning(f"搜索失败 q={q[:40]}: {e}")

    if not raw_results:
        if replace_existing:
            msg = "联网搜索暂无有效结果，无法进行 AI 筛选。请检查搜索引擎配置"
            return [], False, msg, 0
        cached_rows = await _list_cached_news(db, company_id, news_type)
        cached_items = [_news_to_item(n) for n in cached_rows]
        msg = "联网搜索暂无有效结果，无法进行 AI 筛选。请检查搜索引擎配置"
        if cached_items:
            msg += f"；已展示历史入库新闻 {len(cached_items)} 条"
        return cached_items, False, msg, 0

    if replace_existing:
        cleared = await _clear_news_type(db, company_id, news_type)
        if cleared:
            logger.info(
                f"新闻缓存已清空: company={company_id}, type={news_type}, cleared={cleared}"
            )

    all_search_text = "\n\n".join(raw_results)
    items, ai_filtered = await filter_news_with_ai(
        company_name=company_name,
        credit_code=credit_code,
        industry_hint=industry_hint,
        search_results_raw=all_search_text,
        focus_topic=topic,
        filter_mode=mode,
        person_name=person_name,
        exclude_company=company_name if mode == "hobby" else "",
        person_position=person_position,
        hobbies=hobby_list,
        **{**llm_config_kwargs(cfg), "max_tokens": 4096},
    )

    if mode == "hobby":
        before = len(items)
        items = _drop_company_contaminated(items, exclude_keys)
        if before != len(items):
            logger.info(
                f"兴趣硬过滤去掉企业相关 {before - len(items)} 条: topic={topic}"
            )

    new_rows = await _save_news(db, company_id, news_type, items)
    await _vectorize_saved(db, new_rows, cfg)

    cached_rows = await _list_cached_news(db, company_id, news_type)
    need_vec = [n for n in cached_rows if not (n.embedding or "").strip()]
    if need_vec:
        await _vectorize_saved(db, need_vec, cfg)

    all_items = [_news_to_item(n) for n in cached_rows]
    if mode == "hobby":
        all_items = _drop_company_contaminated(all_items, exclude_keys)

    keyword_hint = f"（检索词 {len(queries)} 组）" if queries else ""
    if ai_filtered:
        msg = (
            f"AI 筛选完成{keyword_hint}，新增入库 {len(new_rows)} 条，"
            f"当前共 {len(all_items)} 条"
        )
    else:
        msg = f"AI 过滤暂不可用{keyword_hint}，已尽量保存可用结果"

    return all_items, ai_filtered, msg, len(new_rows)


@router.get("/cached", response_model=NewsResponse)
async def get_cached_news(
    company_id: int,
    news_type: str = "industry",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取已缓存的新闻（从数据库中读取历史搜索记录）"""
    await get_owned_company(company_id, current_user, db)
    rows = await _list_cached_news(db, company_id, news_type)
    items = [_news_to_item(n) for n in rows]
    logger.info(f"缓存新闻: company={company_id}, type={news_type}, {len(items)} 条")
    return NewsResponse(items=items, ai_filtered=True, message="")


@router.get("/industry", response_model=NewsResponse)
async def get_industry_news(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取该企业所属行业的新闻（AI 过滤，入库去重，向量化，返回全量缓存）"""
    company = await get_owned_company(company_id, current_user, db)

    company_name = str(company.name or "")
    credit_code = str(company.credit_code or "")
    industry_hint = _guess_industry(company_name)
    cfg = await get_user_llm_config(current_user, db)
    queries = [
        f"{company_name} {industry_hint} 行业 新闻 最新动态" if industry_hint else f"{company_name} 行业 新闻 动态",
        f"{company_name} 融资 合作 业务 2026",
        f"{company_name} 供应链 上下游 采购 物流" if industry_hint else "",
    ]
    queries = [q for q in queries if q]

    items, ai_filtered, message, saved = await _search_and_filter(
        company_id=company_id,
        company_name=company_name,
        credit_code=credit_code,
        industry_hint=industry_hint,
        news_type="industry",
        queries=queries,
        cfg=cfg,
        db=db,
    )
    logger.info(
        f"行业新闻: {company_name}, AI过滤={'成功' if ai_filtered else '失败'}, "
        f"新增={saved}, 展示={len(items)}"
    )
    return NewsResponse(items=items, ai_filtered=ai_filtered, message=message)


@router.get("/company", response_model=NewsResponse)
async def get_company_news(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取该企业自身的新闻（AI 过滤，入库去重，向量化，返回全量缓存）"""
    company = await get_owned_company(company_id, current_user, db)

    company_name = str(company.name or "")
    credit_code = str(company.credit_code or "")
    industry_hint = _guess_industry(company_name)
    cfg = await get_user_llm_config(current_user, db)
    queries = [
        f"{company_name} {credit_code} 新闻 最新",
        f"{company_name} 融资 财报 业务 产品 2026",
        f"{company_name} 合作 客户 供应商 供应链",
    ]

    items, ai_filtered, message, saved = await _search_and_filter(
        company_id=company_id,
        company_name=company_name,
        credit_code=credit_code,
        industry_hint=industry_hint,
        news_type="company",
        queries=queries,
        cfg=cfg,
        db=db,
    )
    logger.info(
        f"企业新闻: {company_name}, AI过滤={'成功' if ai_filtered else '失败'}, "
        f"新增={saved}, 展示={len(items)}"
    )
    return NewsResponse(items=items, ai_filtered=ai_filtered, message=message)


@router.get("/people", response_model=NewsResponse)
async def get_people_news(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取企业核心人员的相关新闻（AI 过滤，入库去重，向量化，返回全量缓存）"""
    company = await get_owned_company(company_id, current_user, db)

    result = await db.execute(
        select(Person).where(Person.company_id == company_id)
    )
    people = result.scalars().all()

    company_name = str(company.name or "")
    industry_hint = _guess_industry(company_name)
    cfg = await get_user_llm_config(current_user, db)

    person_names = [p.name for p in people[:5] if p.name]
    queries = []
    if person_names:
        queries.append(f"{' '.join(person_names[:3])} {company_name} 新闻 最新")
        queries.append(f"{company_name} 高管 人事变动 2026")
    queries.append(f"{company_name} 核心团队 管理层 动态")

    items, ai_filtered, message, saved = await _search_and_filter(
        company_id=company_id,
        company_name=company_name,
        credit_code=str(company.credit_code or ""),
        industry_hint=industry_hint,
        news_type="people",
        queries=queries,
        cfg=cfg,
        db=db,
    )
    logger.info(
        f"人员新闻: {company_name}, AI过滤={'成功' if ai_filtered else '失败'}, "
        f"新增={saved}, 展示={len(items)}"
    )
    return NewsResponse(items=items, ai_filtered=ai_filtered, message=message)


@router.get("/person/{person_id}/cached-hobbies", response_model=PersonHobbyNewsResponse)
async def get_cached_person_hobby_news(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """读取该人员「企业」标签 + 各兴趣标签已入库新闻（不触发联网搜索）"""
    await get_owned_company(company_id, current_user, db)

    person = await db.get(Person, person_id)
    if not person or person.company_id != company_id:
        raise HTTPException(status_code=404, detail="人员不存在")

    hobbies = parse_hobby_tags(person.hobbies)
    company_name = str(person.company.name if person.company else "")
    credit_code = str(person.company.credit_code if person.company else "")
    exclude_keys = _company_exclude_keywords(company_name, credit_code)
    groups: list[HobbyNewsGroup] = []

    co_rows = await _list_cached_news(db, company_id, company_person_news_type(person_id))
    groups.append(
        HobbyNewsGroup(
            hobby=COMPANY_TAB_LABEL,
            items=[_news_to_item(n) for n in co_rows],
            ai_filtered=True,
            message="",
            kind="company",
        )
    )
    for hobby in hobbies:
        rows = await _list_cached_news(db, company_id, hobby_news_type(person_id, hobby))
        items = _drop_company_contaminated(
            [_news_to_item(n) for n in rows], exclude_keys
        )
        groups.append(
            HobbyNewsGroup(
                hobby=hobby,
                items=items,
                ai_filtered=True,
                message="",
                kind="hobby",
            )
        )
    return PersonHobbyNewsResponse(hobbies=hobbies, groups=groups, message="")


@router.get("/person/{person_id}", response_model=PersonHobbyNewsResponse)
async def get_person_news(
    company_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索人员新闻：自带「企业」标签（企业背景+兴趣交叉）+ 纯兴趣标签（AI 关键词检索）"""
    company = await get_owned_company(company_id, current_user, db)

    person = await db.get(Person, person_id)
    if not person or person.company_id != company_id:
        raise HTTPException(status_code=404, detail="人员不存在")

    company_name = str(company.name or "")
    credit_code = str(company.credit_code or "")
    person_name = str(person.name or "")
    person_position = str(person.position or "")
    hobbies = parse_hobby_tags(person.hobbies)
    industry_hint = _guess_industry(company_name)
    cfg = await get_user_llm_config(current_user, db)
    llm_kw = llm_config_kwargs(cfg)

    groups: list[HobbyNewsGroup] = []
    total_saved = 0
    any_ai = False

    # 1) 「企业」标签
    company_queries, co_kw_ai = await generate_company_person_search_keywords(
        person_name=person_name,
        person_position=person_position,
        company_name=company_name,
        credit_code=credit_code,
        industry_hint=industry_hint,
        hobbies=hobbies,
        **llm_kw,
    )
    co_items, co_ai, co_msg, co_saved = await _search_and_filter(
        company_id=company_id,
        company_name=company_name,
        credit_code=credit_code,
        industry_hint=industry_hint,
        news_type=company_person_news_type(person_id),
        queries=company_queries,
        cfg=cfg,
        db=db,
        focus_topic=person_name,
        filter_mode="company_person",
        person_name=person_name,
        person_position=person_position,
        hobbies=hobbies,
    )
    total_saved += co_saved
    any_ai = any_ai or co_ai or co_kw_ai
    kw_note = "AI 检索词" if co_kw_ai else "默认检索词"
    groups.append(
        HobbyNewsGroup(
            hobby=COMPANY_TAB_LABEL,
            items=co_items,
            ai_filtered=co_ai,
            message=f"{co_msg}；{kw_note}",
            kind="company",
        )
    )
    logger.info(
        f"人员企业新闻: {person_name}, 检索词={company_queries}, "
        f"AI过滤={'成功' if co_ai else '失败'}, 新增={co_saved}, 展示={len(co_items)}"
    )

    # 2) 兴趣标签
    for hobby in hobbies:
        queries, kw_ai = await generate_hobby_search_keywords(hobby, **llm_kw)
        items, ai_filtered, message, saved = await _search_and_filter(
            company_id=company_id,
            company_name=company_name,
            credit_code=credit_code,
            industry_hint="",
            news_type=hobby_news_type(person_id, hobby),
            queries=queries,
            cfg=cfg,
            db=db,
            focus_topic=hobby,
            filter_mode="hobby",
            person_name="",
            hobbies=[hobby],
        )
        total_saved += saved
        any_ai = any_ai or ai_filtered or kw_ai
        kw_note = "AI 检索词" if kw_ai else "默认检索词"
        groups.append(
            HobbyNewsGroup(
                hobby=hobby,
                items=items,
                ai_filtered=ai_filtered,
                message=f"{message}；{kw_note}",
                kind="hobby",
            )
        )
        logger.info(
            f"人员兴趣新闻: {person_name}/{hobby}, 检索词={queries}, "
            f"AI过滤={'成功' if ai_filtered else '失败'}, 新增={saved}, 展示={len(items)}"
        )

    tab_count = 1 + len(hobbies)
    summary = (
        f"已完成企业标签 + {len(hobbies)} 个兴趣标签搜索（共 {tab_count} 组），"
        f"新增入库 {total_saved} 条（已去重并向量化）"
        if any_ai or total_saved
        else "新闻搜索完成，部分标签可能暂无有效结果"
    )
    return PersonHobbyNewsResponse(hobbies=hobbies, groups=groups, message=summary)

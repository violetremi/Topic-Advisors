"""新闻向量存储与检索

使用 LM Studio / OpenAI 兼容的 /v1/embeddings 接口生成向量，
持久化在 News.embedding（JSON），检索时做余弦相似度。
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Optional, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import News

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = "text-embedding-bge-m3"


def _is_local(base_url: str) -> bool:
    u = (base_url or "").lower()
    return any(h in u for h in ("127.0.0.1", "localhost", "0.0.0.0"))


def _news_type_label(news_type: str) -> str:
    """将 news_type 转为向量化/展示用前缀标签。"""
    ntype = (news_type or "").strip()
    if ntype == "industry":
        return "行业新闻"
    if ntype == "company":
        return "企业新闻"
    if ntype == "people":
        return "人员新闻"
    if ntype.endswith("_co"):
        return "人员企业新闻"
    if "_h" in ntype and ntype.startswith("p"):
        return "人员兴趣新闻"
    return "新闻"


def news_to_embed_text(news: News | dict) -> str:
    if isinstance(news, dict):
        title = news.get("title") or ""
        snippet = news.get("snippet") or ""
        reason = news.get("relevance_reason") or ""
        ntype = news.get("news_type") or ""
    else:
        title = news.title or ""
        snippet = news.snippet or ""
        reason = news.relevance_reason or ""
        ntype = news.news_type or ""
    parts = [p for p in (title, snippet, reason) if p]
    prefix = _news_type_label(ntype)
    return f"{prefix}: " + "。".join(parts)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


async def embed_texts(
    texts: list[str],
    *,
    base_url: str,
    api_key: str = "",
    model: str = DEFAULT_EMBED_MODEL,
) -> list[list[float]]:
    """批量调用 embeddings 接口，返回与 texts 同序的向量列表。"""
    if not texts:
        return []

    effective_key = api_key or ("lm-studio" if _is_local(base_url) else "")
    if not effective_key:
        raise RuntimeError("未配置 API Key，无法生成向量")

    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {effective_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "input": texts}

    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        resp = await client.post(url, json=payload, headers=headers)

    if resp.status_code != 200:
        raise RuntimeError(f"embeddings 失败 HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    items = data.get("data") or []
    # 按 index 排序（部分实现可能乱序）
    items = sorted(items, key=lambda x: x.get("index", 0))
    vectors = [it.get("embedding") or [] for it in items]
    if len(vectors) != len(texts):
        raise RuntimeError(f"embeddings 数量不匹配: expect={len(texts)} got={len(vectors)}")
    return vectors


async def vectorize_news_rows(
    db: AsyncSession,
    news_rows: list[News],
    *,
    base_url: str,
    api_key: str = "",
    model: str = DEFAULT_EMBED_MODEL,
) -> int:
    """为新入库新闻生成并写入 embedding，返回成功条数。"""
    pending = [n for n in news_rows if n and not (n.embedding or "").strip()]
    if not pending:
        return 0

    texts = [news_to_embed_text(n) for n in pending]
    try:
        vectors = await embed_texts(
            texts, base_url=base_url, api_key=api_key, model=model
        )
    except Exception as e:
        logger.warning(f"新闻向量化失败（不影响入库）: {e}")
        return 0

    saved = 0
    for news, vec in zip(pending, vectors):
        if not vec:
            continue
        news.embedding = json.dumps(vec, ensure_ascii=False)
        saved += 1

    if saved:
        try:
            await db.commit()
            logger.info(f"新闻向量化完成: {saved}/{len(pending)} 条")
        except Exception as e:
            logger.warning(f"新闻向量写入失败: {e}")
    return saved


async def retrieve_relevant_news(
    db: AsyncSession,
    company_id: int,
    query: str,
    *,
    top_k: int = 12,
    news_type: Optional[str] = None,
    base_url: str = "",
    api_key: str = "",
    model: str = DEFAULT_EMBED_MODEL,
) -> list[dict[str, Any]]:
    """按语义相似度检索企业已入库新闻；向量不可用时按时间倒序回退。"""
    q = select(News).where(News.company_id == company_id)
    if news_type:
        q = q.where(News.news_type == news_type)
    q = q.order_by(News.created_at.desc())
    result = await db.execute(q)
    rows = list(result.scalars().all())
    if not rows:
        return []

    # 没有 embedding 或检索失败 → 时间倒序截断
    async def _fallback() -> list[dict[str, Any]]:
        return [_to_dict(n, score=None) for n in rows[:top_k]]

    with_vec = [n for n in rows if (n.embedding or "").strip()]
    if not with_vec or not base_url or not query.strip():
        return await _fallback()

    try:
        q_vec = (await embed_texts(
            [query], base_url=base_url, api_key=api_key, model=model
        ))[0]
    except Exception as e:
        logger.warning(f"查询向量化失败，回退时间序: {e}")
        return await _fallback()

    scored: list[tuple[float, News]] = []
    for n in with_vec:
        try:
            vec = json.loads(n.embedding)
            if not isinstance(vec, list):
                continue
            score = cosine_similarity(q_vec, vec)
            scored.append((score, n))
        except Exception:
            continue

    if not scored:
        return await _fallback()

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_to_dict(n, score=s) for s, n in scored[:top_k]]


async def fetch_stored_news_for_analysis(
    db: AsyncSession,
    company_id: int,
    company_name: str,
    *,
    base_url: str,
    api_key: str = "",
    model: str = DEFAULT_EMBED_MODEL,
    top_k: int = 16,
    person_id: int | None = None,
    person_ids: list[int] | None = None,
) -> str:
    """综合分析用：向量检索相关入库新闻并格式化为 prompt 文本。

    默认检索该企业全部入库新闻（行业/企业/人员及 p*_co / p*_h*）。
    - person_id：仅返回该人员关联新闻（个人话题分析）
    - person_ids：综合研判场景——合并「行业+企业」与「所选人员」三源新闻，
      保证人员新闻不会被行业/企业新闻在 top_k 中挤掉
    """
    # 综合研判：分源检索后合并
    if person_ids is not None:
        selected = [pid for pid in person_ids if pid]
        result = await db.execute(select(News).where(News.company_id == company_id))
        all_rows = list(result.scalars().all())
        if selected:
            prefixes = {f"p{pid}_" for pid in selected}
            all_rows = [
                n
                for n in all_rows
                if (n.news_type or "") in ("industry", "company", "people")
                or any((n.news_type or "").startswith(p) for p in prefixes)
            ]
        need_vec = [n for n in all_rows if not (n.embedding or "").strip()]
        if need_vec and base_url:
            await vectorize_news_rows(
                db, need_vec, base_url=base_url, api_key=api_key, model=model
            )
        query = (
            f"{company_name} 行业动态 企业新闻 业务进展 融资 合作 政策 "
            "人员动态 兴趣爱好 破冰话题 供应链金融"
        )
        if not selected:
            items = await retrieve_relevant_news(
                db,
                company_id,
                query,
                top_k=top_k,
                news_type=None,
                base_url=base_url,
                api_key=api_key,
                model=model,
            )
            return format_news_for_prompt(
                [x for x in items if x.get("news_type") in ("industry", "company")]
            )
        return await _fetch_merged_news_for_topic_chain(
            db,
            company_id,
            company_name,
            selected,
            query=query,
            base_url=base_url,
            api_key=api_key,
            model=model,
            top_k=top_k,
        )

    # 单人话题分析 / 全企业默认检索
    result = await db.execute(select(News).where(News.company_id == company_id))
    all_rows = list(result.scalars().all())
    if person_id is not None:
        prefix = f"p{person_id}_"
        all_rows = [n for n in all_rows if (n.news_type or "").startswith(prefix)]
    need_vec = [n for n in all_rows if not (n.embedding or "").strip()]
    if need_vec and base_url:
        await vectorize_news_rows(
            db, need_vec, base_url=base_url, api_key=api_key, model=model
        )

    query = (
        f"{company_name} 行业动态 企业新闻 业务进展 融资 合作 政策 "
        "人员动态 兴趣爱好 破冰话题 供应链金融"
    )
    items = await retrieve_relevant_news(
        db,
        company_id,
        query,
        top_k=top_k,
        news_type=None,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    if person_id is not None:
        prefix = f"p{person_id}_"
        items = [x for x in items if str(x.get("news_type") or "").startswith(prefix)]
    return format_news_for_prompt(items)


async def _fetch_merged_news_for_topic_chain(
    db: AsyncSession,
    company_id: int,
    company_name: str,
    person_ids: list[int],
    *,
    query: str,
    base_url: str,
    api_key: str,
    model: str,
    top_k: int,
) -> str:
    """综合研判专用：行业/企业向量新闻 + 所选人员关联向量新闻分源合并。"""
    per_bucket = max(4, top_k // 3)
    person_per = max(3, top_k // max(len(person_ids), 1))

    industry_items = await retrieve_relevant_news(
        db,
        company_id,
        f"{company_name} 行业动态 政策 趋势 供应链金融",
        top_k=per_bucket,
        news_type="industry",
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    company_items = await retrieve_relevant_news(
        db,
        company_id,
        f"{company_name} 企业新闻 业务进展 融资 合作",
        top_k=per_bucket,
        news_type="company",
        base_url=base_url,
        api_key=api_key,
        model=model,
    )

    # 全量语义检索后再按所选人员前缀过滤（覆盖 p*_co / p*_h* / people）
    all_semantic = await retrieve_relevant_news(
        db,
        company_id,
        query,
        top_k=max(top_k, person_per * len(person_ids) + 8),
        news_type=None,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    prefixes = [f"p{pid}_" for pid in person_ids]
    person_items: list[dict[str, Any]] = []
    for item in all_semantic:
        nt = str(item.get("news_type") or "")
        if any(nt.startswith(p) for p in prefixes):
            person_items.append(item)
        if len(person_items) >= person_per * len(person_ids):
            break

    # 若语义检索人员新闻不足，按时间回退补齐所选人员新闻
    if len(person_items) < max(2, len(person_ids)):
        result = await db.execute(
            select(News)
            .where(News.company_id == company_id)
            .order_by(News.created_at.desc())
        )
        seen_ids = {x.get("id") for x in person_items}
        for n in result.scalars().all():
            nt = n.news_type or ""
            if not any(nt.startswith(p) for p in prefixes):
                continue
            if n.id in seen_ids:
                continue
            person_items.append(_to_dict(n, score=None))
            seen_ids.add(n.id)
            if len(person_items) >= person_per * len(person_ids):
                break

    merged: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for bucket in (industry_items, company_items, person_items):
        for item in bucket:
            nid = item.get("id")
            if nid in seen:
                continue
            seen.add(nid)
            merged.append(item)

    return format_news_for_prompt(merged)


def format_news_for_prompt(items: list[dict[str, Any]]) -> str:
    if not items:
        return "（暂无已筛选入库的相关新闻）"

    industry = [x for x in items if x.get("news_type") == "industry"]
    company = [x for x in items if x.get("news_type") == "company"]
    people = [x for x in items if x.get("news_type") == "people"]
    person_company = [
        x for x in items
        if str(x.get("news_type") or "").endswith("_co")
    ]
    person_hobby = [
        x for x in items
        if "_h" in str(x.get("news_type") or "")
        and str(x.get("news_type") or "").startswith("p")
    ]
    known = {"industry", "company", "people"}
    other = [
        x for x in items
        if x.get("news_type") not in known
        and not str(x.get("news_type") or "").endswith("_co")
        and not (
            "_h" in str(x.get("news_type") or "")
            and str(x.get("news_type") or "").startswith("p")
        )
    ]

    def _block(title: str, rows: list[dict]) -> str:
        if not rows:
            return ""
        lines = [f"【{title}】"]
        for i, it in enumerate(rows, 1):
            reason = it.get("relevance_reason") or ""
            score = it.get("score")
            score_s = f"（相关度 {score:.2f}）" if isinstance(score, float) else ""
            lines.append(f"{i}. {it.get('title', '')}{score_s}")
            if reason:
                lines.append(f"   标注: {reason}")
            if it.get("snippet"):
                lines.append(f"   摘要: {it['snippet'][:160]}")
            if it.get("url"):
                lines.append(f"   链接: {it['url']}")
            if it.get("date"):
                lines.append(f"   日期: {it['date']}")
        return "\n".join(lines)

    parts = [
        _block("行业新闻", industry),
        _block("企业新闻", company),
        _block("人员企业新闻（企业背景×兴趣交叉）", person_company),
        _block("人员兴趣新闻", person_hobby),
        _block("人员相关新闻", people),
        _block("其他新闻", other),
    ]
    return "\n\n".join(p for p in parts if p)


def _to_dict(n: News, score: float | None = None) -> dict[str, Any]:
    d = {
        "id": n.id,
        "news_type": n.news_type,
        "title": n.title,
        "url": n.url,
        "snippet": n.snippet or "",
        "date": n.date or "",
        "relevance_reason": n.relevance_reason or "",
    }
    if score is not None:
        d["score"] = float(score)
    return d

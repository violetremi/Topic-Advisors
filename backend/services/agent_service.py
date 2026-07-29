"""
AI Agent 核心服务
-----------------
封装了调用大模型（OpenAI 兼容接口）和多引擎联网搜索的逻辑，
并按照各 Agent 的 prompt 模板组装消息后调用 LLM。
"""
import asyncio
import json
import logging
from typing import Any, Optional

import httpx
from ddgs import DDGS

from config.settings import settings
from config.prompts import AGENT_PROMPTS

# 禁用 ddgs 的 DHT 结果缓存：DDGS 在模块导入时会初始化一个 DhtClient
# （_network_client），一旦某次搜索返回结果就会在「后台线程」里通过
# asyncio.new_event_loop() + set_event_loop() 启动一个全局事件循环做缓存，
# 这会污染 SQLAlchemy 的 greenlet 异步上下文，导致后续 await db.commit() 抛出
# "greenlet_spawn has not been called; can't call await_only() here"。
# 搜索结果缓存对本系统非必需，直接关闭以根除该隐患。
try:
    DDGS._network_client = None
except Exception:  # pragma: no cover - 防御性
    pass

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════
#  搜索配置（运行时更新，无需重启）
# ════════════════════════════════════════════

_SEARCH_CONFIG = {
    "provider": "duckduckgo",
    "api_key": "",
}


def set_search_config(provider: str, api_key: str = ""):
    """设置搜索引擎配置，所有后续搜索将使用该配置"""
    _SEARCH_CONFIG["provider"] = provider or "duckduckgo"
    _SEARCH_CONFIG["api_key"] = api_key or ""
    logger.info(f"搜索引擎已切换为: {_SEARCH_CONFIG['provider']}")


def get_search_config() -> dict:
    return dict(_SEARCH_CONFIG)

# ════════════════════════════════════════════
#  联网搜索（支持多个可配置的搜索引擎）
# ════════════════════════════════════════════

# 后端全局搜索配置，由 web_search 每次调用时通过参数传入
# 或者由调用方从 SystemConfig 加载后传入


def _search_ddgs_sync(query: str, max_results: int = 5) -> list[dict] | None:
    """同步执行 DuckDuckGo 搜索（免费，无需 Key，但在国内网络不稳定）"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results if results else None
    except Exception as e:
        logger.warning(f"DDGS 搜索失败: {e}")
        return None


async def _search_brave(query: str, api_key: str, max_results: int = 8) -> list[dict] | None:
    """Brave Search API（推荐：结果新、质量高，免费 2000 次/月）

    API 申请: https://api.search.brave.com/
    """
    if not api_key:
        logger.warning("Brave 搜索: 未配置 API Key")
        return None

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": max_results,
        "text_format": "plain",
        "freshness": "month",  # 优先最新结果
    }

    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in (data.get("web", {}) or {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "body": item.get("description", ""),
                })
            return results if results else None
        else:
            logger.warning(f"Brave 搜索返回 {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Brave 搜索异常: {e}")
        return None


async def _search_bing(query: str, api_key: str, max_results: int = 8) -> list[dict] | None:
    """Bing Web Search API（Azure 市场，免费 Tier 1000 次/月）

    API 申请: https://www.microsoft.com/en-us/bing/apis/bing-web-search-api
    """
    if not api_key:
        logger.warning("Bing 搜索: 未配置 API Key")
        return None

    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
    }
    params = {
        "q": query,
        "count": max_results,
        "textFormat": "Raw",
        "freshness": "Month",  # 最近一个月
    }

    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in (data.get("webPages", {}) or {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "body": item.get("snippet", ""),
                })
            return results if results else None
        else:
            logger.warning(f"Bing 搜索返回 {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Bing 搜索异常: {e}")
        return None


async def _search_tavily(query: str, api_key: str, max_results: int = 8) -> list[dict] | None:
    """Tavily Search API（适合国内直连，结果质量较好）

    API 申请: https://tavily.com/
    """
    if not api_key:
        logger.warning("Tavily 搜索: 未配置 API Key")
        return None

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("results") or []:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "body": item.get("content", "") or item.get("snippet", ""),
                })
            return results if results else None

        logger.warning(f"Tavily 搜索返回 {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Tavily 搜索异常: {e}")
        return None


async def web_search(
    query: str,
    max_results: int = 5,
    search_provider: str | None = None,
    search_api_key: str | None = None,
) -> str:
    """联网搜索，支持多个搜索引擎后端。

    Args:
        query: 搜索关键词
        max_results: 返回结果上限
        search_provider: 搜索引擎类型，可选 duckduckgo / brave / bing / tavily。
                         为 None 时使用 set_search_config() 设置的全局配置。
        search_api_key: 搜索引擎所需的 API Key（duckduckgo 无需）

    Returns:
        格式化后的搜索文本
    """
    # 使用全局配置（如果调用方没有显式指定）
    provider = search_provider or _SEARCH_CONFIG["provider"]
    api_key = search_api_key or _SEARCH_CONFIG["api_key"]
    results = None

    if provider == "brave":
        logger.info(f"Brave 搜索: {query[:60]}")
        results = await _search_brave(query, api_key, max_results)
    elif provider == "bing":
        logger.info(f"Bing 搜索: {query[:60]}")
        results = await _search_bing(query, api_key, max_results)
    elif provider == "tavily":
        logger.info(f"Tavily 搜索: {query[:60]}")
        results = await _search_tavily(query, api_key, max_results)
    else:
        # duckduckgo（默认）：DDGS + fallback
        logger.info(f"DDGS 搜索: {query[:60]}")
        for attempt in range(2):
            try:
                results = await asyncio.to_thread(_search_ddgs_sync, query, max_results)
                if results:
                    break
            except Exception as e:
                logger.warning(f"DDGS(尝试{attempt+1}): {e}")
                await asyncio.sleep(0.5)

    if results:
        return _format_search_results(results)

    # 全部失败：duckduckgo 还可尝试 fallback
    if provider == "duckduckgo":
        logger.info(f"DDGS 失败，尝试备用搜索引擎: {query[:60]}")
        try:
            results = await asyncio.to_thread(_search_ddgs_fallback, query, max_results)
            if results:
                return _format_search_results(results)
        except Exception:
            pass

    logger.error(f"搜索引擎 [{provider}] 均失败: {query[:60]}")
    return (
        "⚠️ 联网搜索暂时不可用。\n"
        "建议：1) 检查网络连接 2) 在系统设置中配置 Tavily/Brave Search API Key\n"
        "     3) 请稍后重试\n"
    )


def _search_ddgs_fallback(query: str, max_results: int = 5) -> list[dict] | None:
    """DDGS 备用方案：通过 Mojeek 等公开搜索引擎"""
    try:
        with httpx.Client(timeout=10, follow_redirects=True, trust_env=False) as client:
            resp = client.get(
                "https://www.mojeek.com/search",
                params={"q": query, "fmt": "text", "size": max_results},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
            )
            if resp.status_code != 200:
                return None

            results = []
            lines = resp.text.split("\n")
            current = {}
            for line in lines:
                line = line.strip()
                if line.startswith("Title:"):
                    if current.get("title"):
                        results.append(current)
                    current = {"title": line[6:].strip(), "url": "", "body": ""}
                elif line.startswith("URL:"):
                    current["url"] = line[4:].strip()
                elif line.startswith("Description:"):
                    current["body"] = line[12:].strip()
            if current.get("title"):
                results.append(current)
            return results if results else None
    except Exception as e:
        logger.warning(f"Mojeek 备用搜索失败: {e}")
        return None


def _format_search_results(results: list[dict]) -> str:
    """将搜索结果格式化为统一文本"""
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        body = r.get("body", "").strip()
        url_ = r.get("href", "") or r.get("url", "")
        lines.append(f"[{i}] {title}")
        if url_:
            lines.append(f"    来源: {url_}")
        if body:
            lines.append(f"    摘要: {body[:400]}")
        lines.append("")
    return "\n".join(lines)


# ════════════════════════════════════════════
#  大模型调用（含重试机制）
# ════════════════════════════════════════════

# 需要重试的 HTTP 状态码
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    model_override: Optional[str] = None,
    max_retries: int = 2,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    extra_body: Optional[dict] = None,
    assistant_prefill: Optional[str] = None,
    # 以下两个参数仅用于「吸收」经由统一配置字典透传进来的搜索引擎配置，
    # call_llm 本身不调用搜索引擎，调用方会自行把这两个值传给 web_search()。
    search_provider: Optional[str] = None,
    search_api_key: Optional[str] = None,
) -> str:
    """调用 OpenAI 兼容接口，返回回复文本。

    内置重试机制：对 429/5xx 错误自动重试（最多 max_retries 次），
    对其他错误直接返回友好提示。

    优先使用显式传入的 override 参数，否则回退到 settings 中的值。
    extra_body 会合并进请求体（用于关闭本地推理模型 thinking 等）。
    assistant_prefill：对 LM Studio / Qwen 等，可通过预填 assistant 关闭思考并约束输出格式。
    """
    effective_api_key = api_key_override or settings.openai_api_key
    effective_base_url = base_url_override or settings.openai_base_url
    effective_model = model_override or model or settings.llm_model

    # LM Studio 本地服务通常不校验 Key；空 Key 时用占位，避免直接失败
    if not effective_api_key and _is_local_llm(effective_base_url):
        effective_api_key = "lm-studio"

    if not effective_api_key:
        return "（未配置 API Key：请前往系统管理页面配置 LLM 的 API Key）"

    url = f"{effective_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {effective_api_key}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if assistant_prefill:
        messages.append({"role": "assistant", "content": assistant_prefill})

    payload = {
        "model": effective_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra_body:
        payload.update(extra_body)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            # trust_env=False：避免系统代理把 127.0.0.1/localhost 请求劫持成 502
            async with httpx.AsyncClient(timeout=600, trust_env=False) as client:
                resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    return "（模型返回空结果，请检查 API 配置或重试）"

                message = choices[0].get("message", {}) or {}
                content = (message.get("content") or "").strip()
                reasoning = (
                    message.get("reasoning_content")
                    or message.get("reasoning")
                    or ""
                )
                if isinstance(reasoning, dict):
                    reasoning = reasoning.get("content") or ""
                reasoning = (reasoning or "").strip()

                # thinking 吃光 max_tokens 时 content 可能为空
                if not content and reasoning:
                    logger.warning(
                        "LLM content 为空，尝试从 reasoning_content 提取 "
                        f"(reason_len={len(reasoning)})"
                    )
                    content = reasoning

                if not content:
                    finish = choices[0].get("finish_reason")
                    return (
                        "（模型返回内容为空。常见原因：思考模式占用了全部输出 token。"
                        f"finish_reason={finish}。"
                        "请在 LM Studio 关闭 Thinking，或开启 Developer → "
                        "Separate reasoning content in API 后重试）"
                    )

                if assistant_prefill:
                    content = _merge_assistant_prefill(assistant_prefill, content)
                return content

            # 可重试的状态码
            if resp.status_code in _RETRYABLE_STATUSES and attempt < max_retries:
                wait = 2 ** (attempt + 1)  # 指数退避: 2s, 4s
                logger.warning(
                    f"LLM 返回 {resp.status_code}（尝试 {attempt + 1}/{max_retries + 1}），"
                    f"等待 {wait}s 后重试..."
                )
                last_error = f"HTTP {resp.status_code}"
                await asyncio.sleep(wait)
                continue

            # 不可重试的错误：若带有未知参数（旧版 LM Studio），去掉后重试一次
            detail = resp.text[:200]
            if (
                resp.status_code == 400
                and attempt < max_retries
                and extra_body
                and any(
                    k in detail.lower()
                    for k in ("unknown", "unexpected", "extra", "invalid", "reasoning")
                )
            ):
                logger.warning(f"LLM 拒绝 extra_body，去掉后重试: {detail}")
                for k in list(extra_body.keys()):
                    payload.pop(k, None)
                extra_body = None
                last_error = f"HTTP {resp.status_code}"
                continue

            if resp.status_code == 401:
                return "（API Key 认证失败：请在系统管理中检查 API Key 是否正确）"
            elif resp.status_code == 404:
                return f"（模型 '{effective_model}' 不存在或接口地址错误，请检查系统设置）"
            elif resp.status_code == 413:
                return "（请求内容过长，建议减少搜索结果的条数）"
            else:
                logger.error(f"LLM 调用失败 [HTTP {resp.status_code}]: {detail}")
                return f"（LLM 调用失败: HTTP {resp.status_code}，请稍后重试）"

        except httpx.TimeoutException as e:
            last_error = f"超时 ({type(e).__name__})"
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    f"LLM 调用超时（尝试 {attempt + 1}/{max_retries + 1}），"
                    f"等待 {wait}s 后重试..."
                )
                await asyncio.sleep(wait)
                continue
            logger.error(f"LLM 调用超时（已重试 {max_retries} 次）: {e}")
            return (
                "（LLM 调用超时。可能原因：\n"
                "1. 模型负载过高，请稍后重试\n"
                "2. 网络连接不稳定，请检查网络\n"
                "3. 模型规格太小，在系统设置中尝试更大的模型）"
            )

        except httpx.HTTPError as e:
            last_error = f"HTTP错误 ({type(e).__name__})"
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    f"LLM HTTP 错误（尝试 {attempt + 1}/{max_retries + 1}）: {e}"
                )
                await asyncio.sleep(wait)
                continue
            logger.error(f"LLM HTTP 错误（已重试 {max_retries} 次）: {e}")
            return f"（网络请求失败: {type(e).__name__}，请检查网络连接后重试）"

        except Exception as e:
            logger.exception(f"LLM 调用异常 [类型={type(e).__name__}]")
            return f"（LLM 调用异常: {type(e).__name__}，请联系管理员）"

    # 所有重试均失败
    return (
        f"（LLM 调用失败：已自动重试 {max_retries} 次仍不成功。"
        f"最后错误：{last_error}。请稍后重试或检查系统设置）"
    )


def _is_local_llm(base_url: str | None) -> bool:
    u = (base_url or "").lower()
    return any(h in u for h in ("127.0.0.1", "localhost", "0.0.0.0"))


def _merge_assistant_prefill(prefill: str, content: str) -> str:
    """把 assistant 预填与续写拼成完整回复（兼容服务器是否回显 prefill）。"""
    content = (content or "").strip()
    prefill = prefill or ""
    if not prefill:
        return content
    if content.startswith(prefill):
        return content
    # 预填以 [ 结尾、续写以 { 开头 → 拼成完整 JSON 数组
    if prefill.rstrip().endswith("[") and content.lstrip().startswith("{"):
        return prefill.rstrip()[:-1] + "[" + content.lstrip()
    if prefill.rstrip().endswith("[") and content.lstrip().startswith("["):
        return content
    return prefill + content



# ════════════════════════════════════════════
#  各 Agent 分析入口
# ════════════════════════════════════════════

# 行业关键词 → 搜索后缀 映射，帮助 LLM 获得更精准的搜索结果
_INDUSTRY_KEYWORDS = [
    "行业分析", "市场规模", "发展趋势", "竞争格局",
    "产业链", "政策监管", "技术趋势",
]

async def _guess_industry_keywords(company_name: str) -> str:
    """通过企业名称快速猜测所属行业关键词，用于提高搜索命中率"""
    # 常见行业关键词匹配
    INDUSTRY_PATTERNS = [
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
        ("传媒|广告|营销|公关|媒体|影视|娱乐|游戏|体育", "文化传媒"),
        ("制造|工业|机械|设备|化工|材料|钢铁|重工", "制造业"),
        ("酒店|旅游|旅行社|景区|航空|票务|度假", "旅游"),
        ("通信|电信|移动|联通|卫星|基站|5G", "通信"),
        ("法律|咨询|审计|会计|税务|猎头|服务", "专业服务"),
    ]
    for pattern, industry in INDUSTRY_PATTERNS:
        import re
        if re.search(pattern, company_name):
            return industry
    return ""


async def run_industry_analysis(company_name: str, credit_code: str, **llm_kwargs: Any) -> str:
    """行业分析 Agent（增强版）

    1. 先猜测行业归属，构建针对性搜索查询
    2. 多维度并发搜索：行业概况 + 最新动态 + 政策
    3. 组装 prompt 调用 LLM
    """
    prompt_def = AGENT_PROMPTS["industry"]

    # 1. 猜测行业归属
    industry_hint = await _guess_industry_keywords(company_name)
    logger.info(f"行业分析: {company_name}, 推测行业={industry_hint or '未知'}")

    # 2. 多维度并发搜索（3 个查询并行，耗时取最慢者）
    search_queries = [
        f"{company_name} {credit_code} {' '.join(_INDUSTRY_KEYWORDS[:3])}",
        f"{company_name} 最新动态 新闻 2025 2026",
        f"{company_name} {industry_hint} 政策 监管" if industry_hint else f"{company_name} 行业政策 监管",
    ]

    search_results_list = await asyncio.gather(
        *[web_search(q, max_results=4,
                     search_provider=llm_kwargs.get("search_provider"),
                     search_api_key=llm_kwargs.get("search_api_key")) for q in search_queries],
        return_exceptions=True,
    )

    # 3. 合并搜索结果
    all_results_parts = []
    for i, (q, res) in enumerate(zip(search_queries, search_results_list)):
        if isinstance(res, str) and res and "搜索暂时不可用" not in res:
            all_results_parts.append(f"--- 搜索: {q[:40]} ---\n{res}")
        elif isinstance(res, str):
            all_results_parts.append(f"--- 搜索: {q[:40]} ---\n{res}")

    search_results = "\n".join(all_results_parts) if all_results_parts else "（无搜索结果）"

    # 4. 组装 user prompt
    user_prompt = prompt_def["user_prompt_template"].format(
        search_results=search_results,
        company_name=company_name,
        credit_code=credit_code,
        industry_hint=industry_hint or "未知",
    )

    # 5. 调用 LLM
    report = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_kwargs)
    return report


async def run_company_analysis(company_name: str, credit_code: str, **llm_kwargs: Any) -> str:
    """企业分析 Agent（增强版）"""
    prompt_def = AGENT_PROMPTS["company"]

    # 多维度并发搜索
    search_queries = [
        f"{company_name} {credit_code} 经营 财报 风险",
        f"{company_name} 股权结构 实际控制人",
        f"{company_name} 工商信息 注册信息",
    ]
    search_results_list = await asyncio.gather(
        *[web_search(q, max_results=4,
                     search_provider=llm_kwargs.get("search_provider"),
                     search_api_key=llm_kwargs.get("search_api_key")) for q in search_queries],
        return_exceptions=True,
    )

    all_results_parts = []
    for i, (q, res) in enumerate(zip(search_queries, search_results_list)):
        if isinstance(res, str):
            all_results_parts.append(f"--- 搜索: {q[:40]} ---\n{res}")

    search_results = "\n".join(all_results_parts) if all_results_parts else "（无搜索结果）"

    user_prompt = prompt_def["user_prompt_template"].format(
        search_results=search_results,
        company_name=company_name,
        credit_code=credit_code,
    )
    report = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_kwargs)
    return report


async def run_people_analysis(company_name: str, people_list: list, **llm_kwargs: Any) -> str:
    """人员分析 Agent"""
    prompt_def = AGENT_PROMPTS["people"]
    people_json = json.dumps(people_list, ensure_ascii=False, indent=2)
    user_prompt = prompt_def["user_prompt_template"].format(
        people_json=people_json,
        company_name=company_name,
    )
    report = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_kwargs)
    return report


async def run_summary_analysis(
    company_name: str,
    industry_report: str,
    company_report: str,
    people_report: str,
    people_list: list | None = None,
    stored_news: str = "",
    **llm_kwargs: Any,
) -> str:
    """综合研判 Agent（增强版）

    会先联网搜索企业最新动态和核心人员公开信息，
    并结合已入库（向量检索）的新闻，为 LLM 提供可引用链接。

    注：搜索失败不会阻断分析流程，LLM 仍可基于已有报告生成内容。
    """
    prompt_def = AGENT_PROMPTS["summary"]

    # 1. 并发搜索企业最新动态 + 核心人员信息
    search_tasks = []

    # 企业动态搜索（最多 3 路）
    company_queries = [
        f"{company_name} 最新动态 新闻",
        f"{company_name} 2025 2026 融资 业务",
        f"{company_name} 产品 发布 合作",
    ]
    for q in company_queries:
        search_tasks.append(web_search(q, max_results=4,
                                       search_provider=llm_kwargs.get("search_provider"),
                                       search_api_key=llm_kwargs.get("search_api_key")))

    # 人员搜索（如果有人员信息）
    people_search_tasks = []
    if people_list:
        for person in people_list:
            person_name = person.get("name", "")
            if person_name:
                people_search_tasks.append(
                    web_search(f"{person_name} {company_name}", max_results=3,
                              search_provider=llm_kwargs.get("search_provider"),
                              search_api_key=llm_kwargs.get("search_api_key"))
                )

    # 并发执行所有搜索
    all_search_raw = await asyncio.gather(
        *search_tasks, *people_search_tasks,
        return_exceptions=True,
    )

    # 2. 组装搜索结果
    parts = []
    company_results = all_search_raw[:len(company_queries)]
    for i, res in enumerate(company_results):
        if isinstance(res, str):
            parts.append(f"--- 企业动态搜索 #{i+1} ---\n{res}")

    if people_search_tasks:
        people_results = all_search_raw[len(company_queries):]
        for i, (person, res) in enumerate(
            zip([p for p in (people_list or []) if p.get("name")], people_results)
        ):
            if isinstance(res, str):
                parts.append(f"\n--- 人员搜索: {person.get('name', '')} ---\n{res}")

    all_search_results = "\n".join(parts) if parts else "（联网搜索暂无结果，以下分析将基于已有报告与入库新闻）"

    # 3. 序列化人员列表
    people_json = json.dumps(people_list or [], ensure_ascii=False, indent=2)

    # 4. 组装 prompt
    user_prompt = prompt_def["user_prompt_template"].format(
        industry_report=industry_report,
        company_report=company_report,
        people_report=people_report,
        people_json=people_json,
        stored_news=stored_news or "（暂无已筛选入库的相关新闻）",
        search_results=all_search_results,
        company_name=company_name,
    )
    report = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_kwargs)
    return report


async def run_topic_analysis(
    company_name: str,
    person: dict,
    stored_news: str = "",
    **llm_kwargs: Any,
) -> str:
    """人员话题分析 Agent

    1. 搜索该人员的公开信息
    2. 结合 hobbies 等个人信息生成商业+兴趣话题
    """
    from config.prompts import TOPIC_ANALYSIS_AGENT
    prompt_def = TOPIC_ANALYSIS_AGENT

    # 搜索该人员的公开信息
    person_name = person.get("name", "")
    search_results = ""
    if person_name:
        try:
            search_results = await web_search(
                f"{person_name} {company_name}", max_results=5,
                search_provider=llm_kwargs.get("search_provider"),
                search_api_key=llm_kwargs.get("search_api_key"),
            )
        except Exception:
            search_results = "（搜索暂不可用）"

    # 组装 user prompt
    user_prompt = prompt_def["user_prompt_template"].format(
        name=person.get("name", ""),
        position=person.get("position", ""),
        joined_date=person.get("joined_date", ""),
        background=person.get("background", ""),
        hobbies=person.get("hobbies", ""),
        public_links=person.get("public_links", ""),
        notes=person.get("notes", ""),
        stored_news=stored_news or "（暂无已筛选入库的相关新闻）",
        search_results=search_results,
        company_name=company_name,
    )

    report = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_kwargs)
    return report


async def run_topic_chain(
    company_name: str,
    industry_report: str,
    company_report: str,
    person_analyses: list[dict],
    stored_news: str = "",
    **llm_kwargs: Any,
) -> str:
    """综合研判 Agent：联易融拜访沟通策略 + 话题链

    整合行业分析、企业分析、所选人员话题分析，以及行业/企业与人员侧
    向量检索入库新闻，生成联易融团队拜访所选人员的沟通作战指南。
    """
    from config.prompts import TOPIC_CHAIN_AGENT
    prompt_def = TOPIC_CHAIN_AGENT

    # 格式化人员分析
    person_analyses_text = json.dumps(person_analyses, ensure_ascii=False, indent=2)

    user_prompt = prompt_def["user_prompt_template"].format(
        company_name=company_name,
        industry_report=industry_report,
        company_report=company_report,
        person_analyses=person_analyses_text,
        stored_news=stored_news or "（暂无已筛选入库的相关新闻）",
    )

    report = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_kwargs)
    return report


# ════════════════════════════════════════════
#  新闻检索关键词生成（AI）
# ════════════════════════════════════════════

def _parse_string_list_response(response: str) -> list[str]:
    """从 LLM 响应中解析 JSON 字符串数组。"""
    if not response or response.startswith(("（", "(")):
        return []

    clean = _strip_thinking(response)
    candidates = _extract_json_candidates(clean)
    for json_str in candidates:
        for candidate in (json_str, _repair_truncated_json(json_str)):
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, Exception):
                continue
            if not isinstance(parsed, list):
                continue
            out: list[str] = []
            seen: set[str] = set()
            for item in parsed:
                if not isinstance(item, str):
                    continue
                q = item.strip()
                if not q or q in seen:
                    continue
                seen.add(q)
                out.append(q)
            if out:
                return out
    return []


def _llm_json_call_kwargs(llm_kwargs: dict) -> dict:
    """新闻类 JSON 输出的 LLM 调用参数。"""
    base_url = (llm_kwargs.get("base_url_override") or "") + ""
    call_kwargs = {**llm_kwargs, "temperature": 0.2, "max_tokens": 1024}
    if _is_local_llm(base_url):
        call_kwargs["assistant_prefill"] = "<think>\n\n</think>\n["
        call_kwargs["extra_body"] = {
            "reasoning_effort": "none",
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False},
            "top_p": 0.8,
            "top_k": 20,
        }
    return call_kwargs


async def generate_hobby_search_keywords(
    hobby: str,
    **llm_kwargs: Any,
) -> tuple[list[str], bool]:
    """用 AI 为兴趣标签生成新闻检索关键词。返回 (queries, ai_generated)。"""
    from config.prompts import HOBBY_NEWS_KEYWORD_AGENT

    topic = (hobby or "").strip()
    if not topic:
        return [], False

    fallback = [
        f"{topic} 新闻 最新",
        f"{topic} 赛事 活动 动态",
        f"{topic} 联赛 转会 2026",
    ]

    prompt_def = HOBBY_NEWS_KEYWORD_AGENT
    user_prompt = prompt_def["user_prompt_template"].format(hobby=topic)
    response = await call_llm(
        prompt_def["system_prompt"],
        user_prompt,
        **_llm_json_call_kwargs(llm_kwargs),
    )
    keywords = _parse_string_list_response(response)
    if keywords:
        logger.info(f"兴趣关键词 AI 生成: {topic} -> {keywords}")
        return keywords[:5], True

    logger.warning(f"兴趣关键词 AI 解析失败，使用默认模板: {topic}")
    return fallback, False


async def generate_company_person_search_keywords(
    *,
    person_name: str,
    person_position: str,
    company_name: str,
    credit_code: str,
    industry_hint: str,
    hobbies: list[str],
    **llm_kwargs: Any,
) -> tuple[list[str], bool]:
    """用 AI 生成企业背景下结合个人兴趣的新闻检索关键词。"""
    from config.prompts import COMPANY_PERSON_NEWS_KEYWORD_AGENT

    hobbies_text = "、".join(hobbies) if hobbies else "（无）"
    fallback: list[str] = []
    if person_name and company_name:
        fallback.append(f"{person_name} {company_name} 新闻")
        if person_position:
            fallback.append(f"{person_name} {person_position} {company_name}")
        fallback.append(f"{company_name} 高管 人事 动态")
    for hobby in hobbies[:3]:
        if company_name:
            fallback.append(f"{company_name} {hobby} 赞助 活动")
        if person_name:
            fallback.append(f"{person_name} {hobby} 公开活动")

    prompt_def = COMPANY_PERSON_NEWS_KEYWORD_AGENT
    user_prompt = prompt_def["user_prompt_template"].format(
        person_name=person_name or "（未知）",
        position=person_position or "（未知）",
        company_name=company_name or "（未知）",
        credit_code=credit_code or "（未知）",
        industry_hint=industry_hint or "未知",
        hobbies=hobbies_text,
    )
    response = await call_llm(
        prompt_def["system_prompt"],
        user_prompt,
        **_llm_json_call_kwargs(llm_kwargs),
    )
    keywords = _parse_string_list_response(response)
    if keywords:
        logger.info(
            f"企业人员关键词 AI 生成: {person_name}/{company_name} -> {keywords}"
        )
        return keywords[:6], True

    logger.warning(
        f"企业人员关键词 AI 解析失败，使用默认模板: {person_name}/{company_name}"
    )
    return [q for q in fallback if q], False


# ════════════════════════════════════════════
#  新闻过滤（AI 筛选 + 排序）
# ════════════════════════════════════════════

async def filter_news_with_ai(
    company_name: str,
    credit_code: str,
    industry_hint: str,
    search_results_raw: str,
    focus_topic: str = "",
    filter_mode: str = "company",
    person_name: str = "",
    exclude_company: str = "",
    person_position: str = "",
    hobbies: list[str] | None = None,
    **llm_kwargs: Any,
) -> tuple[list, bool]:
    """用 AI 对原始搜索结果进行过滤、排序和标注。

    filter_mode:
      - company: 企业/BD 视角（默认）
      - company_person: 企业背景下结合个人兴趣（人员「企业」标签）
      - hobby: 纯兴趣视角，不带企业过滤规则
    """
    from config.prompts import (
        NEWS_FILTER_AGENT,
        HOBBY_NEWS_FILTER_AGENT,
        COMPANY_PERSON_NEWS_FILTER_AGENT,
    )
    import json

    if not search_results_raw:
        return [], False

    topic = (focus_topic or "").strip()
    mode = (filter_mode or "company").strip().lower()
    hobby_list = hobbies or []
    hobbies_text = "、".join(hobby_list) if hobby_list else "（无）"
    logger.info(
        f"===== AI 新闻过滤开始: mode={mode}, company={company_name}"
        + (f" / 兴趣:{topic}" if topic else "")
        + (f" / 人员:{person_name}" if person_name else "")
        + " ====="
    )
    logger.info(f"搜索结果原文长度: {len(search_results_raw)} 字符")

    if mode == "hobby":
        prompt_def = HOBBY_NEWS_FILTER_AGENT
        user_prompt = prompt_def["user_prompt_template"].format(
            hobby=topic or "兴趣",
            person_name=person_name or "（不限）",
            exclude_company=(exclude_company or company_name or "（无）"),
            search_results=search_results_raw,
        )
    elif mode == "company_person":
        prompt_def = COMPANY_PERSON_NEWS_FILTER_AGENT
        user_prompt = prompt_def["user_prompt_template"].format(
            person_name=person_name or "（未知）",
            position=person_position or "（未知）",
            company_name=company_name,
            credit_code=credit_code,
            industry_hint=industry_hint or "未知",
            hobbies=hobbies_text,
            search_results=search_results_raw,
        )
    else:
        prompt_def = NEWS_FILTER_AGENT
        hint = industry_hint or "未知"
        if topic:
            hint = f"{hint}；关注点:{topic}"
        user_prompt = prompt_def["user_prompt_template"].format(
            company_name=company_name,
            credit_code=credit_code,
            industry_hint=hint,
            search_results=search_results_raw,
        )
        if topic:
            user_prompt = (
                f"Extra focus: 「{topic}」 related to customer {company_name}.\n\n"
                + user_prompt
            )

    # 新闻过滤要稳定 JSON：降低温度；本地 LM Studio/Qwen 用 prefill 关闭 thinking
    base_url = (llm_kwargs.get("base_url_override") or "") + ""
    llm_call_kwargs = {**llm_kwargs, "temperature": 0.15}
    if _is_local_llm(base_url):
        # Qwen thinking 经常吃光 token；API 里 enable_thinking 常被忽略。
        # 用已验证的 assistant 预填：空 think + 强制从 [ 开始输出 JSON。
        llm_call_kwargs["assistant_prefill"] = "<think>\n\n</think>\n["
        llm_call_kwargs["extra_body"] = {
            "reasoning_effort": "none",
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False},
            "top_p": 0.8,
            "top_k": 20,
        }
        # 关闭 thinking 后，输出主要是 JSON，不需要特别长
        if int(llm_call_kwargs.get("max_tokens") or 0) > 4096:
            llm_call_kwargs["max_tokens"] = 4096
    response = await call_llm(prompt_def["system_prompt"], user_prompt, **llm_call_kwargs)

    logger.info(f"===== AI 新闻过滤响应前 200 字符: {response[:200]}... =====")

    # call_llm 失败时返回以全角/半角括号开头的友好错误文案
    if response.startswith(("（", "(")):
        logger.warning(f"新闻过滤 LLM 返回错误: {response[:120]}")
        return _fallback_parse(search_results_raw), False

    clean = _strip_thinking(response)
    candidates = _extract_json_candidates(clean)

    for json_str in candidates:
        for candidate in (json_str, _repair_truncated_json(json_str)):
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, Exception):
                continue
            if not isinstance(parsed, list):
                continue
            validated = _normalize_news_items(parsed)
            if validated:
                logger.info(f"AI 新闻过滤: {company_name}, {len(validated)}/{len(parsed)} 条有效")
                return validated, True

    logger.warning(f"新闻过滤 JSON 解析失败，回退到规则解析: {company_name}")
    return _fallback_parse(search_results_raw), False


def _strip_thinking(text: str) -> str:
    """去掉推理模型的思考内容，尽量只留最终答案。"""
    import re

    clean = text.strip()
    # 常见 think 标签（含未正确闭合时尽量截断到结束后的正文）
    clean = re.sub(r"<think>[\s\S]*?</think>", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"</?think>", "", clean, flags=re.IGNORECASE)
    # Thinking Process / Here's a thinking process 等前缀
    clean = re.sub(
        r"(?:here'?s?\s+a\s+)?thinking\s+process\s*:?[\s\S]*?(?=(\[\s*\{)|```)",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"[这我]?[是就]?[一我]?个?思考[过]?程[：:][\s\S]*?(?=(\[\s*\{)|```)",
        "",
        clean,
    )
    return clean.strip()


def _extract_json(text: str) -> str | None:
    """兼容旧调用：返回最可能的一个 JSON 数组字符串。"""
    cands = _extract_json_candidates(text)
    return cands[0] if cands else None


def _extract_json_candidates(text: str) -> list[str]:
    """提取可能的 JSON 数组候选（优先代码块，再从后往前找 [{...}]）。"""
    import re

    candidates: list[str] = []
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE):
        block = m.group(1).strip()
        if block.startswith("["):
            candidates.append(block)

    # 括号匹配提取完整数组；从后往前优先（最终答案通常在尾部）
    starts: list[int] = []
    for i, ch in enumerate(text):
        if ch == "[" and "{" in text[i : i + 24]:
            starts.append(i)
    for start in reversed(starts):
        sliced = _slice_json_array(text, start)
        if sliced:
            candidates.append(sliced)

    # 去重保序
    seen = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _slice_json_array(text: str, start: int) -> str | None:
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"' and not esc:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    # 未闭合：返回到末尾，交给 _repair_truncated_json
    return text[start:] if depth > 0 else None


def _looks_like_url(value: str) -> bool:
    v = (value or "").strip().lower()
    return v.startswith(("http://", "https://", "//", "www."))


def _first_str(item: dict, *keys: str) -> str:
    for k in keys:
        val = item.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _normalize_news_item(item: dict) -> dict | None:
    """兼容模型常见字段别名（source/summary 等）并规范化为前端结构。"""
    if not isinstance(item, dict):
        return None

    title = _first_str(item, "title", "name", "headline", "新闻标题")
    url = _first_str(item, "url", "link", "href", "source_url", "news_url")
    # 部分模型把链接放在 source；仅当值像 URL 时才采用
    if not url:
        maybe_source = _first_str(item, "source", "来源")
        if _looks_like_url(maybe_source):
            url = maybe_source
    snippet = _first_str(
        item, "snippet", "summary", "body", "description", "content", "摘要", "desc"
    )
    date = _first_str(item, "date", "published_at", "pub_date", "time", "发布时间")
    reason = _first_str(
        item, "relevance_reason", "reason", "why", "relevance", "相关原因", "备注"
    )

    if not title or not url:
        return None
    if not _looks_like_url(url):
        return None

    if url.startswith("//"):
        url = "https:" + url
    elif url.lower().startswith("www."):
        url = "https://" + url

    return {
        "title": title[:500],
        "url": url[:1000],
        "snippet": snippet[:200],
        "date": date[:50],
        "relevance_reason": reason[:200],
    }


def _normalize_news_items(parsed: list) -> list[dict]:
    validated: list[dict] = []
    seen_urls: set[str] = set()
    for item in parsed:
        norm = _normalize_news_item(item) if isinstance(item, dict) else None
        if not norm:
            continue
        if norm["url"] in seen_urls:
            continue
        seen_urls.add(norm["url"])
        validated.append(norm)
    return validated


def _repair_truncated_json(s: str) -> str | None:
    depth_b = 0
    depth_c = 0
    in_str = False
    esc = False
    last = -1
    for i, ch in enumerate(s):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"' and not esc:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "[":
            depth_b += 1
        elif ch == "]":
            depth_b -= 1
        elif ch == "{":
            depth_c += 1
        elif ch == "}":
            depth_c -= 1
        if depth_b == 0 and depth_c == 0:
            last = i + 1
    if last <= 0:
        # 未找到完整闭合点：尝试补全括号
        if depth_b <= 0 and depth_c <= 0:
            return None
        res = s.rstrip().rstrip(",")
        res += "}" * max(0, depth_c)
        res += "]" * max(0, depth_b)
        return res
    res = s[:last]
    res += "}" * max(0, depth_c)
    res += "]" * max(0, depth_b)
    return res


def _fallback_parse(raw: str) -> list[dict]:
    """当 AI 解析失败时的回退方案：简单规则提取"""
    results = []
    lines = raw.split("\n")
    current = {}
    for line in lines:
        line = line.strip()
        if not line:
            if current.get("title"):
                results.append(current)
                current = {}
            continue
        if line.startswith("[") and "]" in line:
            if current.get("title"):
                results.append(current)
            title_start = line.find("] ") + 2
            title = line[title_start:].strip() if title_start < len(line) else ""
            current = {"title": title, "url": "", "snippet": "", "date": "", "relevance_reason": ""}
        elif "来源:" in line:
            url = line.split("来源:", 1)[-1].strip()
            current["url"] = url
        elif "摘要:" in line:
            snippet = line.split("摘要:", 1)[-1].strip()
            current["snippet"] = snippet[:200]

    if current.get("title"):
        results.append(current)

    return results

"""数据库连接与会话管理"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool
from config.settings import settings

logger = logging.getLogger(__name__)

_db_url = settings.database_url
_engine_kwargs: dict = {"echo": False}
# SQLite：并发请求下用 StaticPool，避免默认连接池在回滚后取连接触发 MissingGreenlet
if _db_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    # :memory: 必须 StaticPool；文件库用 NullPool 也可安全支持多并发
    if ":memory:" in _db_url:
        _engine_kwargs["poolclass"] = StaticPool
    else:
        _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(_db_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        from models import Company, Person, Report, CheckRun, PersonAnalysis, TopicChain, News  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    # 增量迁移
    _migrate = [
        ("ALTER TABLE persons ADD COLUMN hobbies TEXT DEFAULT ''",),
        ("ALTER TABLE reports ADD COLUMN batch_id VARCHAR(36) DEFAULT NULL",),
        ("ALTER TABLE check_runs ADD COLUMN batch_id VARCHAR(36) DEFAULT ''",),
        ("ALTER TABLE news ADD COLUMN embedding TEXT DEFAULT ''",),
    ]
    for sql, in _migrate:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception:
            pass  # 字段已存在则忽略

    # 新闻去重唯一索引（已有重复时创建可能失败，忽略即可）
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_news_company_type_url "
                "ON news (company_id, news_type, url)"
            ))
    except Exception:
        pass

    # 去掉历史错误约束 UNIQUE(company_id, url)：会阻止同一 URL 在不同 news_type 下共存
    # （例如 industry 与 p4_co），并导致整批入库 rollback → MissingGreenlet
    await _migrate_drop_news_company_url_unique()

    # 给 check_runs.batch_id 设置 NOT NULL（仅当字段是新增且为 NULL 时才执行）
    try:
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE check_runs SET batch_id = 'legacy' WHERE batch_id IS NULL"))
    except Exception:
        pass


async def _migrate_drop_news_company_url_unique() -> None:
    """SQLite 无法直接 DROP CONSTRAINT，需重建表去掉 uq_company_news_url。"""
    try:
        async with engine.begin() as conn:
            row = await conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='news'"
            ))
            create_sql = (row.scalar() or "")
            if "uq_company_news_url" not in create_sql and "UNIQUE (company_id, url)" not in create_sql:
                return

            logger.info("迁移：重建 news 表，移除 UNIQUE(company_id, url) 约束")
            await conn.execute(text("PRAGMA foreign_keys=OFF"))
            await conn.execute(text(
                """
                CREATE TABLE news_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    news_type VARCHAR(40) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    url VARCHAR(1000) NOT NULL,
                    snippet TEXT,
                    date VARCHAR(50),
                    relevance_reason VARCHAR(200),
                    embedding TEXT DEFAULT '',
                    created_at DATETIME,
                    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
                )
                """
            ))
            await conn.execute(text(
                """
                INSERT INTO news_new (
                    id, company_id, news_type, title, url, snippet, date,
                    relevance_reason, embedding, created_at
                )
                SELECT
                    id, company_id, news_type, title, url, snippet, date,
                    relevance_reason, IFNULL(embedding, ''), created_at
                FROM news
                """
            ))
            await conn.execute(text("DROP TABLE news"))
            await conn.execute(text("ALTER TABLE news_new RENAME TO news"))
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_news_company_type_url "
                "ON news (company_id, news_type, url)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_news_company_type_created "
                "ON news (company_id, news_type, created_at)"
            ))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            logger.info("迁移完成：news 表 UNIQUE(company_id, url) 已移除")
    except Exception as e:
        logger.warning(f"迁移 news 唯一约束失败（可忽略若已完成）: {e}")

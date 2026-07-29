"""数据库模型定义"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_code = Column(String(32), unique=True, nullable=False, comment="企业编号，如 QY20260625-0001")
    name = Column(String(200), nullable=False, comment="企业名称")
    credit_code = Column(String(50), nullable=False, comment="统一社会信用代码")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    persons = relationship("Person", back_populates="company", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="company", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, comment="姓名")
    position = Column(String(200), nullable=False, comment="职位")
    joined_date = Column(String(20), default="", comment="入职时间")
    background = Column(Text, default="", comment="背景描述")
    public_links = Column(Text, default="", comment="公开链接，可存 JSON 或换行分隔")
    notes = Column(Text, default="", comment="备注")
    hobbies = Column(Text, default="", comment="兴趣爱好")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company", back_populates="persons")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String(20), nullable=False, comment="industry / company / people / summary")
    content = Column(Text, nullable=False, comment="完整 Markdown 报告")
    summary = Column(String(200), default="", comment="前 100 字摘要")
    batch_id = Column(String(36), index=True, nullable=True, comment="全量分析批次 ID，用于将同一次分析的4份报告归组")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company", back_populates="reports")


class CheckRun(Base):
    """全量分析核查批次——每次一键全量分析生成一条记录"""
    __tablename__ = "check_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String(36), index=True, nullable=False, comment="批次 UUID，关联 reports 表")
    status = Column(String(20), nullable=False, default="completed", comment="completed / partial / failed")
    summary_text = Column(String(500), default="", comment="本次核查的整体摘要（前500字）")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company")


class PersonAnalysis(Base):
    """人员话题分析——每次生成一条记录"""
    __tablename__ = "person_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False, comment="话题分析内容（Markdown）")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company")
    person = relationship("Person")


class News(Base):
    """搜索到的新闻缓存——按企业分组，按 URL 去重，并持久化向量"""
    __tablename__ = "news"
    __table_args__ = (
        UniqueConstraint("company_id", "news_type", "url", name="uq_news_company_type_url"),
        Index("ix_news_company_type_created", "company_id", "news_type", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    news_type = Column(String(40), nullable=False, comment="industry / company / people / person_{id}")
    title = Column(String(500), nullable=False, comment="新闻标题")
    url = Column(String(1000), nullable=False, comment="新闻原文链接")
    snippet = Column(Text, default="", comment="摘要")
    date = Column(String(50), default="", comment="发布日期")
    relevance_reason = Column(String(200), default="", comment="AI 标注的相关性理由")
    embedding = Column(Text, default="", comment="向量 JSON，用于语义检索")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company")


class TopicChain(Base):
    """综合话题链——一次合成的完整沟通链条"""
    __tablename__ = "topic_chains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False, comment="话题链内容（Markdown）")
    person_ids = Column(String(200), default="", comment="参与的人员ID列表，逗号分隔")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company")


class SystemConfig(Base):
    """系统配置——运行时持久化，无需重启即可生效"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, comment="配置键名")
    value = Column(Text, default="", comment="配置值")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

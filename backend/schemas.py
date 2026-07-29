"""Pydantic 数据模型（请求/响应 schema）"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Company ──
class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="企业名称")
    credit_code: str = Field(..., min_length=1, max_length=50, description="统一社会信用代码")


class CompanyOut(BaseModel):
    id: int
    company_code: str
    name: str
    credit_code: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Person ──
class PersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    position: str = Field(..., min_length=1, max_length=200)
    joined_date: str = ""
    background: str = ""
    public_links: str = ""
    notes: str = ""
    hobbies: str = ""


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    joined_date: Optional[str] = None
    background: Optional[str] = None
    public_links: Optional[str] = None
    notes: Optional[str] = None
    hobbies: Optional[str] = None


class PersonOut(BaseModel):
    id: int
    company_id: int
    name: str
    position: str
    joined_date: str
    background: str
    public_links: str
    notes: str
    hobbies: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Report ──
class ReportOut(BaseModel):
    id: int
    company_id: int
    report_type: str
    content: str
    summary: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── CheckRun ──
class CheckRunListItem(BaseModel):
    id: int
    company_id: int
    status: str
    summary_text: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CheckRunOut(BaseModel):
    id: int
    company_id: int
    status: str
    summary_text: str
    created_at: Optional[datetime] = None
    reports: list[ReportOut] = []

    class Config:
        from_attributes = True


# ── 通用响应 ──
class MessageResponse(BaseModel):
    message: str


# ── News ──
class NewsItem(BaseModel):
    title: str
    url: str
    snippet: str = ""
    date: str = ""
    relevance_reason: str = ""


class NewsResponse(BaseModel):
    items: list[NewsItem] = []
    ai_filtered: bool = False
    message: str = ""


class HobbyNewsGroup(BaseModel):
    hobby: str
    items: list[NewsItem] = []
    ai_filtered: bool = False
    message: str = ""
    # company = 人员自带企业标签；hobby = 兴趣标签
    kind: str = "hobby"


class PersonHobbyNewsResponse(BaseModel):
    """按兴趣爱好标签分组的人员新闻（含自带「企业」标签）"""
    hobbies: list[str] = []
    groups: list[HobbyNewsGroup] = []
    message: str = ""


# ── Topic Analysis ──
class TopicAnalysisOut(BaseModel):
    id: int
    person_id: int
    content: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Topic Chain ──
class TopicChainRequest(BaseModel):
    person_ids: list[int] = []


class TopicChainOut(BaseModel):
    id: int
    company_id: int
    content: str
    person_ids: list[int] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── SystemConfig ──
class SystemConfigItem(BaseModel):
    key: str
    value: str


class SystemConfigOut(BaseModel):
    items: list[SystemConfigItem]


class SystemConfigUpdate(BaseModel):
    items: list[SystemConfigItem]


# ── Auth ──
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名（唯一标识，无密码）")


class LoginResponse(BaseModel):
    username: str
    user_id: int

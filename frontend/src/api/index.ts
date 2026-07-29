/** 后端 API 封装 */
const BASE = '/api';

// ── 轻量鉴权：用户名即身份，存 localStorage ──
const USERNAME_KEY = 'intel_username';

export function getStoredUsername(): string | null {
  return localStorage.getItem(USERNAME_KEY);
}
export function setStoredUsername(username: string): void {
  localStorage.setItem(USERNAME_KEY, username);
}
export function clearStoredUsername(): void {
  localStorage.removeItem(USERNAME_KEY);
}

/** 未登录 / 登录失效时抛出，供 AuthContext 统一处理 */
export class UnauthorizedError extends Error {}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const username = getStoredUsername();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (username) {
    headers['X-Username'] = username;
  }

  const res = await fetch(`${BASE}${url}`, { ...options, headers });

  if (res.status === 401) {
    clearStoredUsername();
    window.dispatchEvent(new Event('intel:unauthorized'));
    const body = await res.json().catch(() => ({}));
    const err = new UnauthorizedError(body.detail || '未登录或登录已失效');
    throw err;
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `请求失败 (${res.status})`);
  }
  return res.json();
}

// ── Auth ──

export interface LoginResponse {
  username: string;
  user_id: number;
}

export function login(username: string) {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username }),
  });
}

// ── Company ──

export interface CompanyItem {
  id: number;
  company_code: string;
  name: string;
  credit_code: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CompanyCreatePayload {
  name: string;
  credit_code: string;
}

export function listCompanies(page = 1, pageSize = 20) {
  return request<CompanyItem[]>(`/companies?page=${page}&page_size=${pageSize}`);
}

export function countCompanies() {
  return request<{ total: number }>('/companies/count');
}

export function getCompany(id: number) {
  return request<CompanyItem>(`/companies/${id}`);
}

export function createCompany(data: CompanyCreatePayload) {
  return request<CompanyItem>('/companies', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Person ──

export interface PersonItem {
  id: number;
  company_id: number;
  name: string;
  position: string;
  joined_date: string;
  background: string;
  public_links: string;
  notes: string;
  hobbies: string;
  created_at: string | null;
}

export interface PersonCreatePayload {
  name: string;
  position: string;
  joined_date?: string;
  background?: string;
  public_links?: string;
  notes?: string;
  hobbies?: string;
}

export function listPersons(companyId: number) {
  return request<PersonItem[]>(`/companies/${companyId}/persons`);
}

export function createPerson(companyId: number, data: PersonCreatePayload) {
  return request<PersonItem>(`/companies/${companyId}/persons`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function deletePerson(companyId: number, personId: number) {
  return request<{ message: string }>(`/companies/${companyId}/persons/${personId}`, {
    method: 'DELETE',
  });
}

// ── Report ──

export interface ReportItem {
  id: number;
  company_id: number;
  report_type: string;
  content: string;
  summary: string;
  created_at: string | null;
}

export function listReportsByType(companyId: number, reportType: string) {
  return request<ReportItem[]>(`/companies/${companyId}/reports/${reportType}`);
}

export function triggerIndustryAnalysis(companyId: number) {
  return request<ReportItem>(`/companies/${companyId}/reports/industry`, {
    method: 'POST',
  });
}

export function triggerCompanyAnalysis(companyId: number) {
  return request<ReportItem>(`/companies/${companyId}/reports/company`, {
    method: 'POST',
  });
}

export function triggerPeopleAnalysis(companyId: number) {
  return request<ReportItem>(`/companies/${companyId}/reports/people`, {
    method: 'POST',
  });
}

export function triggerSummaryAnalysis(companyId: number) {
  return request<ReportItem>(`/companies/${companyId}/reports/summary`, {
    method: 'POST',
  });
}

/** 一键全量分析：按行业→企业→人员→综合研判顺序执行 */
export interface FullAnalysisResult {
  industry: ReportItem;
  company: ReportItem;
  people: ReportItem;
  summary: ReportItem;
  check_run_id?: number;
}

export function triggerFullAnalysis(companyId: number) {
  return request<FullAnalysisResult>(`/companies/${companyId}/reports/full-analysis`, {
    method: 'POST',
  });
}

// ── CheckRun 核查批次 ──

export interface CheckRunItem {
  id: number;
  company_id: number;
  status: string;
  summary_text: string;
  created_at: string | null;
}

export interface CheckRunDetail extends CheckRunItem {
  reports: ReportItem[];
}

export function listCheckRuns(companyId: number) {
  return request<CheckRunItem[]>(`/companies/${companyId}/reports/check-runs`);
}

export function getCheckRun(companyId: number, runId: number) {
  return request<CheckRunDetail>(`/companies/${companyId}/reports/check-runs/${runId}`);
}

// ── System Settings ──

export interface SystemConfigItem {
  key: string;
  value: string;
}

export interface SystemConfigData {
  items: SystemConfigItem[];
}

export function getSettings() {
  return request<SystemConfigData>('/settings');
}

export function updateSettings(items: SystemConfigItem[]) {
  return request<SystemConfigData>('/settings', {
    method: 'PUT',
    body: JSON.stringify({ items }),
  });
}

// ── News ──

export interface NewsItem {
  title: string;
  url: string;
  snippet: string;
  date: string;
  relevance_reason: string;
}

export interface NewsResponse {
  items: NewsItem[];
  ai_filtered: boolean;
  message: string;
}

export interface HobbyNewsGroup {
  hobby: string;
  items: NewsItem[];
  ai_filtered: boolean;
  message: string;
  /** company = 人员自带企业标签；hobby = 兴趣标签 */
  kind?: 'company' | 'hobby' | string;
}


export interface PersonHobbyNewsResponse {
  hobbies: string[];
  groups: HobbyNewsGroup[];
  message: string;
}

export function getIndustryNews(companyId: number) {
  return request<NewsResponse>(`/companies/${companyId}/news/industry`);
}

export function getCompanyNews(companyId: number) {
  return request<NewsResponse>(`/companies/${companyId}/news/company`);
}

export function getPeopleNews(companyId: number) {
  return request<NewsResponse>(`/companies/${companyId}/news/people`);
}

export function getPersonNews(companyId: number, personId: number) {
  return request<PersonHobbyNewsResponse>(`/companies/${companyId}/news/person/${personId}`);
}

export function getCachedPersonHobbyNews(companyId: number, personId: number) {
  return request<PersonHobbyNewsResponse>(
    `/companies/${companyId}/news/person/${personId}/cached-hobbies`
  );
}

export function getCachedNews(companyId: number, newsType: string = "industry") {
  return request<NewsResponse>(`/companies/${companyId}/news/cached?news_type=${newsType}`);
}

// ── Person Topic Analysis ──

export interface TopicAnalysisItem {
  id: number | null;
  person_id: number;
  content: string;
  created_at: string | null;
}

export function getTopicAnalysis(companyId: number, personId: number) {
  return request<TopicAnalysisItem>(`/companies/${companyId}/persons/${personId}/topic-analysis`);
}

export function createTopicAnalysis(companyId: number, personId: number) {
  return request<TopicAnalysisItem>(`/companies/${companyId}/persons/${personId}/topic-analysis`, {
    method: 'POST',
  });
}

// ── Topic Chain ──

export interface TopicChainItem {
  id: number | null;
  company_id: number;
  content: string;
  person_ids: number[];
  created_at: string | null;
}

export function getLatestTopicChain(companyId: number) {
  return request<TopicChainItem>(`/companies/${companyId}/topic-chain/latest`);
}

export function createTopicChain(companyId: number, personIds: number[]) {
  return request<TopicChainItem>(`/companies/${companyId}/topic-chain`, {
    method: 'POST',
    body: JSON.stringify({ person_ids: personIds }),
  });
}

export function listTopicChains(companyId: number) {
  return request<TopicChainItem[]>(`/companies/${companyId}/topic-chain`);
}

// ── Person (update existing person) ──

export function updatePerson(companyId: number, personId: number, data: Partial<PersonCreatePayload>) {
  return request<PersonItem>(`/companies/${companyId}/persons/${personId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Spin,
  message,
  notification,
  Typography,
  Empty,
  Tag,
  Card,
  Space,
  Divider,
  Tooltip,
  Steps,
} from 'antd';
import {
  ArrowLeftOutlined,
  BankOutlined,
  ProfileOutlined,
  TeamOutlined,
  MergeCellsOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  UserOutlined,
  CheckCircleFilled,
  ClockCircleFilled,
  MinusCircleFilled,
  HistoryOutlined,
  RightCircleOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import {
  getCompany,
  CompanyItem,
  listReportsByType,
  triggerIndustryAnalysis,
  triggerCompanyAnalysis,
  triggerPeopleAnalysis,
  triggerSummaryAnalysis,
  triggerFullAnalysis,
  listCheckRuns,
  getCheckRun,
  listPersons,
  PersonItem,
  ReportItem,
  CheckRunItem,
  CheckRunDetail,
} from '../api';
import ReportContent from '../components/ReportTimeline';
import PersonTable from '../components/PersonTable';

const { Title, Text } = Typography;

// ── 报告类型定义 ──
interface ReportTypeInfo {
  key: string;
  label: string;
  icon: React.ReactNode;
  color: string;
  description: string;
}

const REPORT_TYPES: ReportTypeInfo[] = [
  { key: 'industry', label: '行业分析', icon: <BankOutlined />, color: '#1677ff', description: '分析企业所属行业的现状、趋势、竞争格局与风险' },
  { key: 'company', label: '企业分析', icon: <ProfileOutlined />, color: '#52c41a', description: '深入诊断企业经营状况、核心竞争力与发展前景' },
  { key: 'people', label: '人员分析', icon: <TeamOutlined />, color: '#722ed1', description: '基于核心团队构成分析战略导向与稳定性' },
  { key: 'summary', label: '综合研判', icon: <MergeCellsOutlined />, color: '#fa8c16', description: '融合行业、企业、人员三份报告提炼深度洞察' },
];

// ── 步骤定义 ──
interface StepInfo {
  key: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}

const ANALYSIS_STEPS: StepInfo[] = [
  { key: 'person', title: '录入人员', description: '添加核心人员', icon: <UserOutlined /> },
  { key: 'industry', title: '行业分析', description: '行业现状与趋势', icon: <BankOutlined /> },
  { key: 'company', title: '企业分析', description: '经营状况诊断', icon: <ProfileOutlined /> },
  { key: 'people', title: '人员分析', description: '团队稳定性评估', icon: <TeamOutlined /> },
  { key: 'summary', title: '综合研判', description: '融合生成洞察', icon: <MergeCellsOutlined /> },
];

/** 获取报告状态 */
function getReportStatus(report: ReportItem | null, loading: boolean, dependenciesMet: boolean): {
  statusText: string;
  statusColor: string;
  icon: React.ReactNode;
} {
  if (loading) return { statusText: '分析中…', statusColor: 'processing', icon: <LoadingOutlined style={{ color: '#1677ff' }} /> };
  if (report) return { statusText: '已完成', statusColor: 'success', icon: <CheckCircleFilled style={{ color: '#52c41a' }} /> };
  if (!dependenciesMet) return { statusText: '待准备', statusColor: 'warning', icon: <MinusCircleFilled style={{ color: '#faad14' }} /> };
  return { statusText: '未开始', statusColor: 'default', icon: <MinusCircleFilled style={{ color: '#d9d9d9' }} /> };
}

/** 截取报告前 120 字作为摘要 */
function getSummary(report: ReportItem | null): string {
  if (!report) return '';
  const clean = report.content
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/[#*\n]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return clean.slice(0, 120) + (clean.length > 120 ? '…' : '');
}

// ══════════════════════════════════════
//  分析步骤子组件 - 单个分析步骤
// ══════════════════════════════════════

const AnalysisStepCard: React.FC<{
  reportType: ReportTypeInfo;
  report: ReportItem | null;
  isRunning: boolean;
  depsOk: boolean;
  expanded: boolean;
  onTrigger: () => void;
  onToggleExpand: () => void;
}> = ({ reportType: rt, report, isRunning, depsOk, expanded, onTrigger, onToggleExpand }) => {
  const status = getReportStatus(report, isRunning, depsOk);

  return (
    <Card
      style={{
        borderRadius: 10,
        border: expanded ? `2px solid ${rt.color}` : '1px solid #f0f0f0',
        marginBottom: 16,
        transition: 'all 0.2s',
      }}
      styles={{ body: { padding: 20 } }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Space size={12}>
          <span style={{ fontSize: 22, color: rt.color }}>{rt.icon}</span>
          <div>
            <Text strong style={{ fontSize: 15, display: 'block' }}>{rt.label}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{rt.description}</Text>
          </div>
        </Space>
        <Space>
          <Tag color={status.statusColor} style={{ marginRight: 0 }}>
            {status.icon} {status.statusText}
          </Tag>
        </Space>
      </div>

      {/* 依赖不满足提示 */}
      {!depsOk && (
        <div style={{ background: '#fffbe6', border: '1px dashed #faad14', borderRadius: 6, padding: '10px 14px', marginBottom: 12 }}>
          <Text type="warning">
            {rt.key === 'people' ? '⚠️ 请先在「录入人员」步骤添加至少一位核心人员' : '⚠️ 请先完成前置分析步骤'}
          </Text>
        </div>
      )}

      {/* 报告摘要或占位 */}
      {!expanded && report && (
        <div
          style={{ background: '#fafafa', borderRadius: 6, padding: '10px 14px', marginBottom: 12, cursor: 'pointer' }}
          onClick={onToggleExpand}
        >
          <Text type="secondary" style={{ fontSize: 13 }}>{getSummary(report)}</Text>
        </div>
      )}

      {!expanded && !report && (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#bfbfbf' }}>
          {depsOk ? '点击下方按钮启动 AI 分析' : '前置条件未满足'}
        </div>
      )}

      {/* 操作按钮 */}
      <div style={{ display: 'flex', gap: 8 }}>
        {report && (
          <Button
            type={expanded ? 'primary' : 'default'}
            size="small"
            icon={expanded ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={onToggleExpand}
          >
            {expanded ? '收起报告' : '查看报告'}
          </Button>
        )}
        <Button
          type="primary"
          size="small"
          ghost={!!report}
          icon={<ThunderboltOutlined />}
          loading={isRunning}
          disabled={!depsOk || isRunning}
          onClick={onTrigger}
        >
          {isRunning ? '分析中…' : report ? '重新分析' : '开始分析'}
        </Button>
      </div>

      {/* 展开的报告内容 */}
      {expanded && report && (
        <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
          <ReportContent report={report} reportTypeLabel={rt.label} />
        </div>
      )}
    </Card>
  );
};

// ══════════════════════════════════════
//  主页面
// ══════════════════════════════════════

const CompanyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const companyId = Number(id);

  const [company, setCompany] = useState<CompanyItem | null>(null);
  const [loading, setLoading] = useState(true);

  // ── 步骤导航 ──
  const [currentStep, setCurrentStep] = useState(0);

  // ── 报告数据 ──
  const [industryReport, setIndustryReport] = useState<ReportItem | null>(null);
  const [companyReport, setCompanyReport] = useState<ReportItem | null>(null);
  const [peopleReport, setPeopleReport] = useState<ReportItem | null>(null);
  const [summaryReport, setSummaryReport] = useState<ReportItem | null>(null);
  const [personCount, setPersonCount] = useState(0);

  // ── 分析运行状态 ──
  const [runningType, setRunningType] = useState<string | null>(null);
  const [isFullRunning, setIsFullRunning] = useState(false);
  const [fullProgress, setFullProgress] = useState<string[]>([]);

  // ── 核查历史 ──
  const [checkRuns, setCheckRuns] = useState<CheckRunItem[]>([]);
  const [checkRunsLoading, setCheckRunsLoading] = useState(false);
  const [expandedRun, setExpandedRun] = useState<number | null>(null);
  const [expandedRunReports, setExpandedRunReports] = useState<{ [runId: number]: CheckRunDetail | null }>({});

  // ── 展开的报告 ──
  const [expandedReport, setExpandedReport] = useState<string | null>(null);

  // ── 人员刷新 key（强制 PersonTable 重载）──
  const [personRefreshKey, setPersonRefreshKey] = useState(0);

  // ── 加载企业信息 ──

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    getCompany(companyId)
      .then(setCompany)
      .catch((e) => message.error('获取企业信息失败: ' + (e.message || '')))
      .finally(() => setLoading(false));
  }, [companyId]);

  // ── 并行加载所有报告 ──

  const fetchAllReports = useCallback(async () => {
    if (!companyId) return;
    const types = ['industry', 'company', 'people', 'summary'];
    const setters = [setIndustryReport, setCompanyReport, setPeopleReport, setSummaryReport];

    const results = await Promise.allSettled(
      types.map((t) => listReportsByType(companyId, t))
    );

    results.forEach((result, idx) => {
      if (result.status === 'fulfilled') {
        const reports = result.value;
        setters[idx](reports.length > 0 ? reports[0] : null);
      } else {
        setters[idx](null);
      }
    });

    // 获取人员数量
    try {
      const persons = await listPersons(companyId);
      setPersonCount(persons.length);
    } catch {
      setPersonCount(0);
    }
  }, [companyId]);

  useEffect(() => {
    fetchAllReports();
  }, [fetchAllReports]);

  // ── 触发分析 ──

  const handleTrigger = async (type: string) => {
    setRunningType(type);
    try {
      let result: ReportItem;
      switch (type) {
        case 'industry':
          result = await triggerIndustryAnalysis(companyId);
          setIndustryReport(result);
          break;
        case 'company':
          result = await triggerCompanyAnalysis(companyId);
          setCompanyReport(result);
          break;
        case 'people':
          result = await triggerPeopleAnalysis(companyId);
          setPeopleReport(result);
          break;
        case 'summary':
          result = await triggerSummaryAnalysis(companyId);
          setSummaryReport(result);
          break;
        default:
          return;
      }
      message.success(`${REPORT_TYPES.find((t) => t.key === type)?.label}完成`);
      setExpandedReport(type);
      // 分析完成后自动前进到下一步（如果不是综合研判）
      const stepIndex = ANALYSIS_STEPS.findIndex((s) => s.key === type);
      if (stepIndex >= 1 && stepIndex < 4) {
        setCurrentStep(stepIndex + 1);
      }
    } catch (e: any) {
      const errorMsg = e.message || '分析失败';
      if (errorMsg.includes('API Key') || errorMsg.includes('认证')) {
        notification.error({
          message: 'API 配置错误',
          description: 'LLM API Key 认证失败，请前往「系统管理」页面检查 API Key 和接口地址配置是否正确。',
          duration: 8,
        });
      } else if (errorMsg.includes('超时')) {
        notification.warning({
          message: '分析超时',
          description: 'LLM 响应超时，可能原因：模型负载过高或网络不稳定。建议稍后重试，或在系统设置中尝试更快的模型。',
          duration: 8,
        });
      } else if (errorMsg.includes('网络')) {
        notification.warning({
          message: '网络错误',
          description: '网络请求失败，请检查网络连接后重试。',
          duration: 6,
        });
      } else if (errorMsg.includes('不存在') || errorMsg.includes('404')) {
        notification.error({
          message: '模型配置错误',
          description: `模型不存在或接口地址错误：${errorMsg}，请前往「系统管理」页面检查配置。`,
          duration: 8,
        });
      } else {
        message.error(errorMsg, 6);
      }
    } finally {
      setRunningType(null);
    }
  };

  // ── 一键全量分析 ──

  const handleFullAnalysis = async () => {
    setIsFullRunning(true);
    setFullProgress([]);
    try {
      const result = await triggerFullAnalysis(companyId);
      const steps = ['industry', 'company', 'people', 'summary'] as const;
      type ReportStep = typeof steps[number];
      const setters: Record<ReportStep, (r: ReportItem) => void> = {
        industry: setIndustryReport,
        company: setCompanyReport,
        people: setPeopleReport,
        summary: setSummaryReport,
      };
      const labels: Record<string, string> = {
        industry: '行业分析',
        company: '企业分析',
        people: '人员分析',
        summary: '综合研判',
      };
      for (const step of steps) {
        const report = result[step];
        if (report) {
          setters[step](report);
          setFullProgress(prev => [...prev, labels[step]]);
        }
      }
      message.success('全量分析完成！');
      setExpandedReport('summary');
      setCurrentStep(4);
      fetchCheckRuns();
    } catch (e: any) {
      const errorMsg = e.message || '全量分析失败';
      if (errorMsg.includes('API Key') || errorMsg.includes('认证')) {
        notification.error({
          message: 'API 配置错误',
          description: 'LLM API Key 认证失败，请前往「系统管理」页面检查 API Key 和接口地址配置是否正确。',
          duration: 10,
        });
      } else if (errorMsg.includes('超时')) {
        notification.warning({
          message: '分析超时',
          description: 'LLM 响应超时，已自动重试。建议稍后网络状况更好时重试，或在系统设置中选择更快的模型。',
          duration: 10,
        });
      } else {
        notification.warning({
          message: '全量分析中断',
          description: `${errorMsg}\n已完成的分析已自动保存，请稍后重试剩余部分。`,
          duration: 8,
        });
      }
    } finally {
      setIsFullRunning(false);
    }
  };

  // ── 核查历史 ──

  const fetchCheckRuns = useCallback(async () => {
    if (!companyId) return;
    setCheckRunsLoading(true);
    try {
      const data = await listCheckRuns(companyId);
      setCheckRuns(data);
    } catch { /* ignore */ }
    finally { setCheckRunsLoading(false); }
  }, [companyId]);

  const handleExpandRun = async (runId: number) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
      return;
    }
    setExpandedRun(runId);
    if (!expandedRunReports[runId]) {
      try {
        const detail = await getCheckRun(companyId, runId);
        setExpandedRunReports(prev => ({ ...prev, [runId]: detail }));
      } catch {
        message.error('加载核查详情失败');
      }
    }
  };

  useEffect(() => {
    fetchCheckRuns();
  }, [fetchCheckRuns]);

  // ── 依赖检查 ──

  const dependenciesMet = {
    industry: true,
    company: true,
    people: personCount > 0,
    summary: !!(industryReport && companyReport && peopleReport),
  };

  // ── 各步骤完成状态 ──
  const stepStatuses = ANALYSIS_STEPS.map((s, i) => {
    if (s.key === 'person') {
      return personCount > 0 ? 'finish' as const : (i === currentStep ? 'process' as const : 'wait' as const);
    }
    const reportMap: Record<string, ReportItem | null> = {
      industry: industryReport,
      company: companyReport,
      people: peopleReport,
      summary: summaryReport,
    };
    const report = reportMap[s.key];
    if (report) return 'finish' as const;
    if (i === currentStep) return 'process' as const;
    return 'wait' as const;
  });

  // ── 已完成报告数 ──
  const completedCount = [industryReport, companyReport, peopleReport, summaryReport].filter(Boolean).length;

  // ── 加载中状态 ──

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!company) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Empty description="企业不存在" />
        <Button onClick={() => navigate('/companies')} style={{ marginTop: 16 }}>返回列表</Button>
      </div>
    );
  }

  // ── 渲染 ──

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      {/* 返回按钮 */}
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/companies')} style={{ marginBottom: 16, padding: 0 }}>
        返回列表
      </Button>

      {/* ── 企业信息头 ── */}
      <Card
        style={{ borderRadius: 12, marginBottom: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
        styles={{ body: { padding: '16px 24px' } }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <Space size={12} align="center" style={{ marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>{company.name}</Title>
              {completedCount > 0 && (
                <Tag icon={<CheckCircleFilled />} color="success" style={{ marginRight: 0 }}>
                  已分析 {completedCount}/4
                </Tag>
              )}
            </Space>
            <Text type="secondary" style={{ fontSize: 13 }}>
              编号：{company.company_code}
              <Divider type="vertical" />
              信用代码：{company.credit_code}
              <Divider type="vertical" />
              创建时间：{company.created_at ? new Date(company.created_at).toLocaleString('zh-CN') : '-'}
            </Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={fetchAllReports} size="small">
            刷新报告
          </Button>
        </div>
      </Card>

      {/* ── 步骤导航 ── */}
      <div style={{ background: '#fff', borderRadius: 12, padding: '24px 32px', marginBottom: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Steps
          current={currentStep}
          status={currentStep === 0 && personCount > 0 ? 'process' : 'process'}
          items={ANALYSIS_STEPS.map((s, i) => ({
            title: s.title,
            description: s.description,
            status: stepStatuses[i],
            icon: stepStatuses[i] === 'finish' ? <CheckCircleOutlined /> : s.icon,
          }))}
          onChange={(step) => {
            // 不允许跳过未完成的步骤
            const minAllowed = Math.max(
              0,
              ...ANALYSIS_STEPS.slice(0, step).map((ss, si) => {
                if (ss.key === 'person') return personCount > 0 ? si : Infinity;
                const reportMap: Record<string, ReportItem | null> = {
                  industry: industryReport,
                  company: companyReport,
                  people: peopleReport,
                  summary: summaryReport,
                };
                return reportMap[ss.key] ? si : Infinity;
              })
            );
            if (minAllowed === Infinity && step > 0) {
              message.warning('请按顺序完成前置步骤');
              return;
            }
            setCurrentStep(step);
            setExpandedReport(null);
          }}
        />
      </div>

      {/* ── 步骤内容区 ── */}
      <Card
        style={{ borderRadius: 12, minHeight: 400, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
        styles={{ body: { padding: 24 } }}
      >
        {/* ═══ 步骤 0: 录入人员 ═══ */}
        {currentStep === 0 && (
          <div>
            <div style={{ marginBottom: 20 }}>
              <Title level={4} style={{ margin: 0 }}>
                <UserOutlined style={{ marginRight: 8 }} />
                核心人员列表
              </Title>
              <Text type="secondary">添加企业核心人员信息，后续将基于人员数据生成人员分析报告</Text>
            </div>

            {personCount === 0 && (
              <Card
                size="small"
                style={{ marginBottom: 20, border: '1px dashed #faad14', background: '#fffbe6', borderRadius: 8 }}
              >
                <Space>
                  <span style={{ fontSize: 18, color: '#faad14' }}>⚠️</span>
                  <Text strong style={{ color: '#ad6800' }}>尚未录入任何核心人员</Text>
                  <Text type="warning">请添加至少一位人员，否则无法进行人员分析和综合研判</Text>
                </Space>
              </Card>
            )}

            <PersonTable key={personRefreshKey} companyId={companyId} onChange={(c) => setPersonCount(c)} />

            {/* 底部提示和操作 */}
            <Divider style={{ margin: '20px 0 16px 0' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text type="secondary" style={{ fontSize: 13 }}>
                已录入 <Text strong>{personCount}</Text> 位核心人员
                {personCount > 0 ? ' ✓ 可进行下一步分析' : '，请添加后进入分析步骤'}
              </Text>
              <Button
                type="primary"
                disabled={personCount === 0}
                onClick={() => setCurrentStep(1)}
              >
                下一步：开始分析 {personCount > 0 ? '(已就绪)' : '(需添加人员)'}
              </Button>
            </div>
          </div>
        )}

        {/* ═══ 步骤 1-4: 分析步骤 ═══ */}
        {currentStep >= 1 && currentStep <= 4 && (
          <div>
            {/* 进度标签栏 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <div>
                <Title level={4} style={{ margin: 0 }}>
                  {ANALYSIS_STEPS[currentStep].icon}
                  <span style={{ marginLeft: 8 }}>{ANALYSIS_STEPS[currentStep].title}</span>
                </Title>
                <Text type="secondary">
                  {currentStep === 4
                    ? '融合行业、企业、人员三份报告生成综合研判'
                    : REPORT_TYPES[currentStep - 1]?.description || '分析步骤'}
                </Text>
              </div>

              {/* 全量分析按钮 */}
              {personCount > 0 && (
                <Space>
                  {isFullRunning && fullProgress.length > 0 && (
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      进度: {fullProgress.join(' → ')}
                    </Text>
                  )}
                  <Button
                    type="primary"
                    ghost
                    icon={<ThunderboltOutlined />}
                    loading={isFullRunning}
                    disabled={isFullRunning}
                    onClick={handleFullAnalysis}
                  >
                    {isFullRunning ? '全量分析中…' : '一键全量分析（1→4）'}
                  </Button>
                </Space>
              )}
            </div>

            {/* 逐一渲染分析卡片 */}
            {(() => {
              const reportTypes = currentStep === 4
                ? REPORT_TYPES  // 综合研判显示全部
                : [REPORT_TYPES[currentStep - 1]];
              return reportTypes.map((rt) => {
                const reportMap: Record<string, ReportItem | null> = {
                  industry: industryReport,
                  company: companyReport,
                  people: peopleReport,
                  summary: summaryReport,
                };
                const report = reportMap[rt.key];
                const isRunning = runningType === rt.key;
                const depsOk = dependenciesMet[rt.key as keyof typeof dependenciesMet];
                const isExpanded = expandedReport === rt.key;

                // 完成状态指示
                const isComplete = !!report;

                return (
                  <div key={rt.key} style={{ marginBottom: 12 }}>
                    {/* 步骤快捷指示条 */}
                    {currentStep === 4 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 16, color: rt.color }}>{rt.icon}</span>
                        <Text strong style={{ fontSize: 14 }}>{rt.label}</Text>
                        {isComplete ? (
                          <Tag icon={<CheckCircleFilled />} color="success" style={{ marginLeft: 4 }}>已完成</Tag>
                        ) : isRunning ? (
                          <Tag icon={<LoadingOutlined />} color="processing">分析中</Tag>
                        ) : (
                          <Tag icon={<MinusCircleFilled />}>未开始</Tag>
                        )}
                      </div>
                    )}

                    <AnalysisStepCard
                      reportType={rt}
                      report={report}
                      isRunning={isRunning}
                      depsOk={depsOk}
                      expanded={isExpanded}
                      onTrigger={() => handleTrigger(rt.key)}
                      onToggleExpand={() => setExpandedReport(isExpanded ? null : rt.key)}
                    />
                  </div>
                );
              });
            })()}

            {/* 步骤导航按钮 */}
            <Divider style={{ margin: '16px 0 0 0' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 16 }}>
              <Button onClick={() => setCurrentStep(currentStep - 1)}>
                上一步
              </Button>
              {currentStep < 4 ? (
                <Button type="primary" onClick={() => setCurrentStep(currentStep + 1)}>
                  下一步
                </Button>
              ) : (
                <Button onClick={() => setCurrentStep(0)}>
                  回到人员录入
                </Button>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* ── 核查历史 ── */}
      {completedCount > 0 && (
        <div style={{ marginTop: 24 }}>
          <Divider style={{ marginBottom: 16 }} />
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 15 }}>
                <HistoryOutlined style={{ marginRight: 6 }} />
                核查历史
                <Text type="secondary" style={{ fontWeight: 400, fontSize: 13, marginLeft: 8 }}>
                  {checkRuns.length > 0 ? `共 ${checkRuns.length} 次` : '暂无核查记录'}
                </Text>
              </span>
              <Button size="small" icon={<ReloadOutlined />} onClick={(e) => { e.stopPropagation(); fetchCheckRuns(); }}>
                刷新
              </Button>
            </div>

            {checkRunsLoading && checkRuns.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 16 }}><Spin size="small" /></div>
            ) : checkRuns.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 13, display: 'block', textAlign: 'center', padding: 16 }}>
                点击「开始分析」或「一键全量分析」后，每次分析结果将记录在此处
              </Text>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {checkRuns.map((run) => {
                  const isExpanded = expandedRun === run.id;
                  const runDetail = expandedRunReports[run.id];
                  return (
                    <Card
                      key={run.id}
                      size="small"
                      style={{
                        borderRadius: 8,
                        border: isExpanded ? '1px solid #1677ff' : '1px solid #f0f0f0',
                      }}
                      styles={{ body: { padding: '12px 16px' } }}
                    >
                      <div
                        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                        onClick={() => handleExpandRun(run.id)}
                      >
                        <Space>
                          <Tag color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'processing'}>
                            {run.status === 'completed' ? '已完成' : run.status === 'failed' ? '失败' : '运行中'}
                          </Tag>
                          <Text style={{ fontSize: 13 }}>
                            {run.created_at ? new Date(run.created_at).toLocaleString('zh-CN') : '-'}
                          </Text>
                          {run.summary_text && (
                            <Text type="secondary" style={{ fontSize: 12, maxWidth: 400 }} ellipsis>
                              {run.summary_text}
                            </Text>
                          )}
                        </Space>
                        <RightCircleOutlined
                          rotate={isExpanded ? 90 : 0}
                          style={{ color: '#8c8c8c', fontSize: 14, transition: 'transform 0.2s' }}
                        />
                      </div>

                      {isExpanded && (
                        <div style={{ marginTop: 12, borderTop: '1px solid #f5f5f5', paddingTop: 12 }}>
                          {runDetail ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                              {['industry', 'company', 'people', 'summary'].map((type) => {
                                const report = runDetail.reports.find((r) => r.report_type === type);
                                const rt = REPORT_TYPES.find((t) => t.key === type)!;
                                return (
                                  <div
                                    key={type}
                                    style={{
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      padding: '6px 8px',
                                      background: '#fafafa',
                                      borderRadius: 6,
                                    }}
                                  >
                                    <Space>
                                      <span style={{ color: rt.color, fontSize: 14 }}>{rt.icon}</span>
                                      <Text style={{ fontSize: 13 }}>{rt.label}</Text>
                                      {report ? (
                                        <Tag color="success" style={{ fontSize: 11, marginLeft: 4 }}>已生成</Tag>
                                      ) : (
                                        <Tag style={{ fontSize: 11, marginLeft: 4 }}>缺失</Tag>
                                      )}
                                    </Space>
                                    {report && (
                                      <Button
                                        type="link"
                                        size="small"
                                        icon={<EyeOutlined />}
                                        onClick={() => setExpandedReport(type)}
                                        style={{ padding: 0 }}
                                      >
                                        查看
                                      </Button>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <div style={{ textAlign: 'center', padding: 8 }}>
                              <Spin size="small" />
                            </div>
                          )}
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CompanyDetail;

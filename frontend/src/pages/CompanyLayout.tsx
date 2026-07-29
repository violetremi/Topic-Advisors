import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { Tabs, Spin, Typography, Card, Tag, Space, Button, message, Empty, Divider } from 'antd';
import {
  ArrowLeftOutlined,
  BankOutlined,
  ProfileOutlined,
  TeamOutlined,
  MergeCellsOutlined,
  ReloadOutlined,
  CheckCircleFilled,
  MinusCircleFilled,
} from '@ant-design/icons';
import {
  getCompany,
  CompanyItem,
  listReportsByType,
  listPersons,
  getLatestTopicChain,
  getCachedNews,
  ReportItem,
  NewsItem,
} from '../api';

const { Title, Text } = Typography;

const TAB_ITEMS = [
  { key: 'industry', label: '行业分析', icon: <BankOutlined />, color: '#1677ff' },
  { key: 'company', label: '企业分析', icon: <ProfileOutlined />, color: '#52c41a' },
  { key: 'people', label: '人员分析', icon: <TeamOutlined />, color: '#722ed1' },
  { key: 'summary', label: '综合研判', icon: <MergeCellsOutlined />, color: '#fa8c16' },
];

const CompanyLayout: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const companyId = Number(id);

  const [company, setCompany] = useState<CompanyItem | null>(null);
  const [loading, setLoading] = useState(true);

  // Status indicators for each tab
  const [reportStatus, setReportStatus] = useState<Record<string, boolean>>({
    industry: false,
    company: false,
    people: false,
  });
  const [personCount, setPersonCount] = useState(0);
  const [chainExists, setChainExists] = useState(false);

  // ── 跨 Tab 保持新闻状态 ──
  const [industryNews, setIndustryNews] = useState<NewsItem[]>([]);
  const [industryNewsSearched, setIndustryNewsSearched] = useState(false);
  const [companyNews, setCompanyNews] = useState<NewsItem[]>([]);
  const [companyNewsSearched, setCompanyNewsSearched] = useState(false);

  // Load cached news on mount
  useEffect(() => {
    if (!companyId) return;
    getCachedNews(companyId, 'industry').then((r) => {
      if (r.items.length > 0) { setIndustryNews(r.items); setIndustryNewsSearched(true); }
    }).catch(() => {});
    getCachedNews(companyId, 'company').then((r) => {
      if (r.items.length > 0) { setCompanyNews(r.items); setCompanyNewsSearched(true); }
    }).catch(() => {});
  }, [companyId]);

  // Determine active tab from URL path
  const pathSegment = location.pathname.split('/').pop() || '';
  const activeTab = TAB_ITEMS.find((t) => t.key === pathSegment)?.key || 'industry';

  // Load company info
  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    getCompany(companyId)
      .then(setCompany)
      .catch((e) => message.error('获取企业信息失败: ' + (e.message || '')))
      .finally(() => setLoading(false));
  }, [companyId]);

  // Load status of all analyses
  const loadStatus = useCallback(async () => {
    if (!companyId) return;
    try {
      const [industryReports, companyReports, peopleReports, persons, chain] = await Promise.all([
        listReportsByType(companyId, 'industry'),
        listReportsByType(companyId, 'company'),
        listReportsByType(companyId, 'people'),
        listPersons(companyId),
        getLatestTopicChain(companyId).catch(() => null),
      ]);

      setReportStatus({
        industry: industryReports.length > 0,
        company: companyReports.length > 0,
        people: peopleReports.length > 0,
      });
      setPersonCount(persons.length);
      setChainExists(!!(chain && chain.content));
    } catch {
      // silent
    }
  }, [companyId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleTabChange = (key: string) => {
    navigate(`/companies/${companyId}/${key}`);
  };

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
        <Button onClick={() => navigate('/companies')} style={{ marginTop: 16 }}>
          返回列表
        </Button>
      </div>
    );
  }

  // Compute completed count
  const completedCount = Object.values(reportStatus).filter(Boolean).length;
  const summaryReady = reportStatus.industry && reportStatus.company && reportStatus.people && personCount > 0;

  // Build tab items with status badges
  const tabs = TAB_ITEMS.map((tab) => {
    let statusIcon = null;
    if (tab.key === 'people') {
      statusIcon = personCount > 0
        ? <CheckCircleFilled style={{ color: '#52c41a', fontSize: 12, marginLeft: 4 }} />
        : <MinusCircleFilled style={{ color: '#d9d9d9', fontSize: 12, marginLeft: 4 }} />;
    } else if (tab.key === 'summary') {
      statusIcon = chainExists
        ? <CheckCircleFilled style={{ color: '#52c41a', fontSize: 12, marginLeft: 4 }} />
        : summaryReady
          ? null
          : <MinusCircleFilled style={{ color: '#d9d9d9', fontSize: 12, marginLeft: 4 }} />;
    } else {
      statusIcon = reportStatus[tab.key]
        ? <CheckCircleFilled style={{ color: '#52c41a', fontSize: 12, marginLeft: 4 }} />
        : <MinusCircleFilled style={{ color: '#d9d9d9', fontSize: 12, marginLeft: 4 }} />;
    }

    return {
      key: tab.key,
      label: (
        <span>
          {tab.icon}
          <span style={{ marginLeft: 6 }}>{tab.label}</span>
          {statusIcon}
        </span>
      ),
    };
  });

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* 返回按钮 */}
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/companies')}
        style={{ marginBottom: 16, padding: 0 }}
      >
        返回列表
      </Button>

      {/* 企业信息头 */}
      <Card
        style={{
          borderRadius: 12,
          marginBottom: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        }}
        styles={{ body: { padding: '16px 24px' } }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div>
            <Space size={12} align="center" style={{ marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>
                {company.name}
              </Title>
              {completedCount > 0 && (
                <Tag icon={<CheckCircleFilled />} color="success" style={{ marginRight: 0 }}>
                  已分析 {completedCount}/3
                </Tag>
              )}
            </Space>
            <Text type="secondary" style={{ fontSize: 13 }}>
              编号：{company.company_code}
              <Divider type="vertical" />
              信用代码：{company.credit_code}
              <Divider type="vertical" />
              人员：{personCount} 人
            </Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={loadStatus} size="small">
            刷新状态
          </Button>
        </div>
      </Card>

      {/* Tab 导航 */}
      <Card
        style={{
          borderRadius: 12,
          minHeight: 500,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        }}
        styles={{ body: { padding: '16px 24px' } }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          items={tabs}
          size="large"
        />
        {/* 子路由内容 */}
        <Outlet context={{
          companyId,
          company,
          loadStatus,
          industryNews, setIndustryNews,
          industryNewsSearched, setIndustryNewsSearched,
          companyNews, setCompanyNews,
          companyNewsSearched, setCompanyNewsSearched,
        }} />
      </Card>
    </div>
  );
};

export default CompanyLayout;

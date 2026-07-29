import React, { useEffect, useState } from 'react';
import { useParams, useOutletContext } from 'react-router-dom';
import { Button, Spin, message, Typography, Tag, Space, Empty, Alert } from 'antd';
import {
  ThunderboltOutlined,
  ProfileOutlined,
  CheckCircleFilled,
  SearchOutlined,
} from '@ant-design/icons';
import {
  listReportsByType,
  triggerCompanyAnalysis,
  getCompanyNews,
  getCachedNews,
  ReportItem,
  NewsItem,
} from '../api';
import ReportContent from '../components/ReportTimeline';
import NewsTimeline from '../components/NewsTimeline';

const { Title, Text } = Typography;

interface OutletContext {
  companyId: number;
  company: { name: string };
  loadStatus: () => void;
  companyNews: NewsItem[];
  setCompanyNews: (items: NewsItem[]) => void;
  companyNewsSearched: boolean;
  setCompanyNewsSearched: (v: boolean) => void;
}

const CompanyAnalysisDetail: React.FC = () => {
  const { companyId, company, loadStatus, companyNews, setCompanyNews, companyNewsSearched, setCompanyNewsSearched } = useOutletContext<OutletContext>();

  const [report, setReport] = useState<ReportItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const [newsLoading, setNewsLoading] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    listReportsByType(companyId, 'company')
      .then((reports) => setReport(reports.length > 0 ? reports[0] : null))
      .catch(() => message.error('加载企业分析报告失败'))
      .finally(() => setLoading(false));
  }, [companyId]);

  const handleSearchNews = async () => {
    setNewsLoading(true);
    try {
      const resp = await getCompanyNews(companyId);
      setCompanyNews(resp.items);
      setCompanyNewsSearched(true);
      if (resp.message) {
        if (resp.items.length === 0 || !resp.ai_filtered) {
          message.info(resp.message);
        } else {
          message.success(resp.message);
        }
      } else if (resp.items.length === 0) {
        message.info('暂无匹配的企业新闻');
      }
    } catch (e: any) {
      message.error('搜索企业新闻失败: ' + (e.message || ''));
    } finally {
      setNewsLoading(false);
    }
  };

  const handleTrigger = async () => {
    setRunning(true);
    try {
      const result = await triggerCompanyAnalysis(companyId);
      setReport(result);
      message.success('企业分析完成');
      loadStatus();
    } catch (e: any) {
      message.error(e.message || '分析失败');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      {/* 操作栏 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20,
        }}
      >
        <Space size={12}>
          <ProfileOutlined style={{ fontSize: 22, color: '#52c41a' }} />
          <div>
            <Title level={4} style={{ margin: 0 }}>
              企业分析
            </Title>
            <Text type="secondary">深入诊断企业经营状况、核心竞争力与发展前景</Text>
          </div>
        </Space>
        <Space>
          {report && (
            <Tag icon={<CheckCircleFilled />} color="success">
              已生成
            </Tag>
          )}
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={running}
            onClick={handleTrigger}
          >
            {running ? '分析中…' : report ? '重新分析' : '开始分析'}
          </Button>
        </Space>
      </div>

      {/* 报告内容 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : report ? (
        <div style={{ marginBottom: 24 }}>
          <ReportContent report={report} reportTypeLabel="企业分析报告" />
        </div>
      ) : (
        <div
          style={{
            textAlign: 'center',
            padding: 60,
            background: '#fafafa',
            borderRadius: 10,
            marginBottom: 24,
            border: '1px dashed #d9d9d9',
          }}
        >
          <Empty description="暂无企业分析报告" />
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            点击上方「开始分析」按钮生成企业分析报告
          </Text>
        </div>
      )}

      {/* 新闻区域 - 手动触发 */}
      <div style={{ marginTop: 32 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <Title level={5} style={{ margin: 0 }}>
            <ProfileOutlined style={{ marginRight: 8, color: '#52c41a' }} />
            企业新闻
          </Title>
          <Button
            icon={<SearchOutlined />}
            loading={newsLoading}
            onClick={handleSearchNews}
          >
            {newsLoading ? 'AI 搜索筛选中…' : companyNewsSearched ? '重新搜索' : '搜索企业新闻'}
          </Button>
        </div>
        {companyNewsSearched && (
          <NewsTimeline news={companyNews} loading={newsLoading} title="" />
        )}
        {!companyNewsSearched && (
          <Alert
            message="点击「搜索企业新闻」，AI 筛选结果会入库去重并持续展示；综合分析时将结合这些新闻做向量检索"
            type="info"
            showIcon
            style={{ borderRadius: 8 }}
          />
        )}
      </div>
    </div>
  );
};

export default CompanyAnalysisDetail;

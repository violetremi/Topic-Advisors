import React, { useEffect, useState } from 'react';
import { useParams, useOutletContext } from 'react-router-dom';
import { Button, Spin, message, Typography, Tag, Space, Empty, Alert } from 'antd';
import {
  ThunderboltOutlined,
  BankOutlined,
  CheckCircleFilled,
  LoadingOutlined,
  MinusCircleFilled,
  SearchOutlined,
} from '@ant-design/icons';
import {
  listReportsByType,
  triggerIndustryAnalysis,
  getIndustryNews,
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
  industryNews: NewsItem[];
  setIndustryNews: (items: NewsItem[]) => void;
  industryNewsSearched: boolean;
  setIndustryNewsSearched: (v: boolean) => void;
}

const IndustryDetail: React.FC = () => {
  const { companyId, company, loadStatus, industryNews, setIndustryNews, industryNewsSearched, setIndustryNewsSearched } = useOutletContext<OutletContext>();

  const [report, setReport] = useState<ReportItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const [newsLoading, setNewsLoading] = useState(false);

  // Load existing report
  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    listReportsByType(companyId, 'industry')
      .then((reports) => setReport(reports.length > 0 ? reports[0] : null))
      .catch(() => message.error('加载行业分析报告失败'))
      .finally(() => setLoading(false));
  }, [companyId]);

  // Manual news search（不清空已有列表，搜索期间持续展示历史入库新闻）
  const handleSearchNews = async () => {
    setNewsLoading(true);
    try {
      const resp = await getIndustryNews(companyId);
      setIndustryNews(resp.items);
      setIndustryNewsSearched(true);
      if (resp.message) {
        if (resp.items.length === 0 || !resp.ai_filtered) {
          message.info(resp.message);
        } else {
          message.success(resp.message);
        }
      } else if (resp.items.length === 0) {
        message.info('暂无匹配的行业新闻');
      }
    } catch (e: any) {
      message.error('搜索行业新闻失败: ' + (e.message || ''));
    } finally {
      setNewsLoading(false);
    }
  };

  const handleTrigger = async () => {
    setRunning(true);
    try {
      const result = await triggerIndustryAnalysis(companyId);
      setReport(result);
      message.success('行业分析完成');
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
          <BankOutlined style={{ fontSize: 22, color: '#1677ff' }} />
          <div>
            <Title level={4} style={{ margin: 0 }}>
              行业分析
            </Title>
            <Text type="secondary">分析企业所属行业的现状、趋势、竞争格局与风险</Text>
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
          <ReportContent report={report} reportTypeLabel="行业分析报告" />
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
          <Empty description="暂无行业分析报告" />
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            点击上方「开始分析」按钮生成行业分析报告
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
            <BankOutlined style={{ marginRight: 8, color: '#1677ff' }} />
            行业新闻
          </Title>
          <Button
            icon={<SearchOutlined />}
            loading={newsLoading}
            onClick={handleSearchNews}
          >
            {newsLoading ? 'AI 搜索筛选中…' : industryNewsSearched ? '重新搜索' : '搜索行业新闻'}
          </Button>
        </div>
        {industryNewsSearched && (
          <NewsTimeline news={industryNews} loading={newsLoading} title="" />
        )}
        {!industryNewsSearched && (
          <Alert
            message="点击「搜索行业新闻」，AI 筛选结果会入库去重并持续展示；综合分析时将结合这些新闻做向量检索"
            type="info"
            showIcon
            style={{ borderRadius: 8 }}
          />
        )}
      </div>
    </div>
  );
};

export default IndustryDetail;

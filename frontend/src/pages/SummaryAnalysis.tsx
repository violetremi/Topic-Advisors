import React, { useEffect, useState } from 'react';
import { useParams, useOutletContext } from 'react-router-dom';
import {
  Button,
  Spin,
  message,
  Typography,
  Space,
  Card,
  Checkbox,
  Tag,
  Empty,
  Divider,
  Alert,
  List,
} from 'antd';
import {
  MergeCellsOutlined,
  ThunderboltOutlined,
  CheckCircleFilled,
  UserOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import {
  listPersons,
  getLatestTopicChain,
  createTopicChain,
  listTopicChains,
  PersonItem,
  TopicChainItem,
} from '../api';
import ReportContent from '../components/ReportTimeline';

const { Title, Text } = Typography;

interface OutletContext {
  companyId: number;
  company: { name: string };
  loadStatus: () => void;
}

const SummaryAnalysis: React.FC = () => {
  const { companyId, company, loadStatus } = useOutletContext<OutletContext>();

  const [persons, setPersons] = useState<PersonItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [generating, setGenerating] = useState(false);

  const [chain, setChain] = useState<TopicChainItem | null>(null);
  const [chainLoading, setChainLoading] = useState(false);
  const [history, setHistory] = useState<TopicChainItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Load persons and existing chain
  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    Promise.all([
      listPersons(companyId),
      getLatestTopicChain(companyId).catch(() => null),
    ])
      .then(([persons, latest]) => {
        setPersons(persons);
        if (latest && latest.content) setChain(latest);
      })
      .catch(() => message.error('加载信息失败'))
      .finally(() => setLoading(false));

    // Load history
    setHistoryLoading(true);
    listTopicChains(companyId)
      .then(setHistory)
      .catch(() => {/* silent */})
      .finally(() => setHistoryLoading(false));
  }, [companyId]);

  const handleGenerate = async () => {
    if (selectedIds.length === 0) {
      message.warning('请至少选择一位人员');
      return;
    }
    setGenerating(true);
    try {
      const result = await createTopicChain(companyId, selectedIds);
      setChain(result);
      message.success('沟通策略与话题链生成完成');
      loadStatus();

      // Refresh history
      const hist = await listTopicChains(companyId);
      setHistory(hist);
    } catch (e: any) {
      message.error(e.message || '生成失败');
    } finally {
      setGenerating(false);
    }
  };

  const togglePerson = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

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
          <MergeCellsOutlined style={{ fontSize: 22, color: '#fa8c16' }} />
          <div>
            <Title level={4} style={{ margin: 0 }}>
              综合研判
            </Title>
            <Text type="secondary">
              融合行业/企业分析、向量化新闻与所选人员关联新闻，生成联易融拜访沟通策略与话题链
            </Text>
          </div>
        </Space>
        <Space>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={generating}
            disabled={selectedIds.length === 0}
            onClick={handleGenerate}
          >
            {generating ? '生成中…' : '生成沟通策略与话题链'}
          </Button>
        </Space>
      </div>

      {/* 人员选择区域 */}
      <Card
        size="small"
        style={{
          marginBottom: 20,
          borderRadius: 10,
          border: '1px solid #f0f0f0',
        }}
        styles={{ body: { padding: '16px 20px' } }}
      >
        <div style={{ marginBottom: 12 }}>
          <Text strong>
            <UserOutlined style={{ marginRight: 6 }} />
            选择联易融团队拟拜访的人员
          </Text>
          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
            已选 {selectedIds.length} 人
          </Text>
        </div>

        {persons.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无人员数据，请先在「人员分析」模块添加人员"
          />
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {persons.map((p) => (
              <Tag
                key={p.id}
                style={{
                  padding: '4px 12px',
                  cursor: 'pointer',
                  userSelect: 'none',
                  fontSize: 13,
                  borderRadius: 6,
                  border: selectedIds.includes(p.id)
                    ? '1px solid #722ed1'
                    : '1px solid #d9d9d9',
                  background: selectedIds.includes(p.id) ? '#f9f0ff' : '#fafafa',
                }}
                onClick={() => togglePerson(p.id)}
              >
                <Checkbox
                  checked={selectedIds.includes(p.id)}
                  style={{ marginRight: 6 }}
                />
                {p.name}
                <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                  {p.position}
                </Text>
              </Tag>
            ))}
          </div>
        )}
      </Card>

      {/* 提示信息 */}
      {selectedIds.length === 0 && (
        <Alert
          message="请先勾选拟拜访的人员"
          description="将结合行业分析、企业分析中的向量化新闻，以及所选人员关联的向量化新闻，以联易融拜访为背景生成沟通策略与话题链。"
          type="info"
          showIcon
          style={{ marginBottom: 20, borderRadius: 8 }}
        />
      )}

      <Divider style={{ margin: '0 0 20px 0' }} />

      {/* 话题链内容 */}
      {chainLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : chain ? (
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 12,
            }}
          >
            <Space>
              <CheckCircleFilled style={{ color: '#52c41a', fontSize: 16 }} />
              <Title level={5} style={{ margin: 0 }}>
                最新沟通策略与话题链
              </Title>
              {chain.created_at && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {new Date(chain.created_at).toLocaleString('zh-CN')}
                </Text>
              )}
            </Space>
          </div>
          <Card
            style={{
              borderRadius: 10,
              border: '1px solid #f0f0f0',
            }}
            styles={{ body: { padding: '20px 24px' } }}
          >
            <ReportContent
              report={chain as any}
              reportTypeLabel="联易融拜访沟通指南"
            />
          </Card>
        </div>
      ) : (
        <div
          style={{
            textAlign: 'center',
            padding: 60,
            background: '#fafafa',
            borderRadius: 10,
            border: '1px dashed #d9d9d9',
          }}
        >
          <Empty description="暂无综合研判结果" />
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            请先勾选人员，然后点击「生成沟通策略与话题链」
          </Text>
        </div>
      )}

      {/* 历史记录 */}
      {history.length > 1 && (
        <div style={{ marginTop: 32 }}>
          <Divider />
          <Title level={5} style={{ marginBottom: 12 }}>
            历史研判记录
          </Title>
          <List
            size="small"
            dataSource={history.filter((h) => h.id !== chain?.id)}
            loading={historyLoading}
            renderItem={(item) => (
              <List.Item
                style={{ cursor: 'pointer', padding: '8px 12px', borderRadius: 6 }}
                onClick={() => setChain(item)}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color="orange">研判 #{item.id}</Tag>
                      {item.person_ids && item.person_ids.length > 0 && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          涉及 {item.person_ids.length} 人
                        </Text>
                      )}
                    </Space>
                  }
                  description={
                    item.created_at
                      ? new Date(item.created_at).toLocaleString('zh-CN')
                      : ''
                  }
                />
              </List.Item>
            )}
          />
        </div>
      )}
    </div>
  );
};

export default SummaryAnalysis;

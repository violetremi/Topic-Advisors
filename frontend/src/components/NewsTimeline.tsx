import React from 'react';
import { Typography, Empty, Spin, Timeline, Tag, Tooltip } from 'antd';
import {
  GlobalOutlined,
  ClockCircleOutlined,
  BulbOutlined,
  ThunderboltOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import type { NewsItem } from '../api';

const { Text, Title } = Typography;

interface Props {
  news: NewsItem[];
  loading: boolean;
  title?: string;
}

/** 根据 relevance_reason 返回对应的标签颜色和图标 */
function getReasonTag(reason: string): { color: string; icon: React.ReactNode; label: string } {
  const r = reason.toLowerCase();
  if (r.includes('商机') || r.includes('融资') || r.includes('合作')) {
    return { color: 'red', icon: <ThunderboltOutlined />, label: '商机线索' };
  }
  if (r.includes('交叉') || r.includes('赞助') || r.includes('csr')) {
    return { color: 'orange', icon: <TeamOutlined />, label: '兴趣交叉' };
  }
  if (r.includes('破冰') || r.includes('话题') || r.includes('兴趣')) {
    return { color: 'purple', icon: <TeamOutlined />, label: '破冰话题' };
  }
  if (r.includes('情报') || r.includes('行业') || r.includes('趋势') || r.includes('政策')) {
    return { color: 'blue', icon: <BulbOutlined />, label: '行业情报' };
  }
  return { color: 'default', icon: null, label: '' };
}

const NewsTimeline: React.FC<Props> = ({ news, loading, title = '相关新闻' }) => {
  return (
    <div
      style={{
        background: '#fafafa',
        borderRadius: 10,
        padding: '20px 24px',
        border: '1px solid #f0f0f0',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <Title level={5} style={{ margin: 0 }}>
          <GlobalOutlined style={{ marginRight: 8, color: '#1677ff' }} />
          {title}
        </Title>
        {!loading && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 {news.length} 条 · AI 筛选
          </Text>
        )}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="small" style={{ marginRight: 8 }} />
          <Text type="secondary">AI 正在搜索和筛选相关新闻…</Text>
        </div>
      ) : news.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<Text type="secondary">暂无相关新闻</Text>}
          style={{ margin: '20px 0' }}
        />
      ) : (
        <Timeline
          items={news.map((item, index) => {
            const reasonTag = getReasonTag(item.relevance_reason || '');
            return {
              key: index,
              dot: <ClockCircleOutlined style={{ fontSize: 12, color: '#1677ff' }} />,
              children: (
                <div style={{ marginBottom: 4 }}>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      fontSize: 14,
                      fontWeight: 500,
                      color: '#1677ff',
                      textDecoration: 'none',
                      display: 'block',
                      marginBottom: 4,
                      lineHeight: 1.4,
                    }}
                  >
                    {item.title || '（无标题）'}
                  </a>
                  {item.snippet && (
                    <Text
                      type="secondary"
                      style={{
                        fontSize: 12,
                        display: 'block',
                        lineHeight: 1.5,
                        color: '#8c8c8c',
                      }}
                    >
                      {item.snippet.slice(0, 200)}
                      {item.snippet.length > 200 ? '…' : ''}
                    </Text>
                  )}
                  <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                    {item.date && (
                      <Text type="secondary" style={{ fontSize: 11, color: '#bfbfbf' }}>
                        <ClockCircleOutlined style={{ marginRight: 2 }} />
                        {item.date}
                      </Text>
                    )}
                    {reasonTag.label && (
                      <Tooltip
                        title={
                          item.relevance_reason || 'AI 判断此条新闻对 BD 场景有价值'
                        }
                      >
                        <Tag
                          color={reasonTag.color}
                          style={{ fontSize: 10, lineHeight: '16px', padding: '0 6px', margin: 0 }}
                        >
                          {reasonTag.icon}
                          <span style={{ marginLeft: 2 }}>{reasonTag.label}</span>
                        </Tag>
                      </Tooltip>
                    )}
                  </div>
                </div>
              ),
            };
          })}
        />
      )}
    </div>
  );
};

export default NewsTimeline;

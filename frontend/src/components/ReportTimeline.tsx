import React from 'react';
import { Typography } from 'antd';
import ReactMarkdown from 'react-markdown';
import { ClockCircleOutlined, FileTextOutlined } from '@ant-design/icons';
import type { ReportItem } from '../api';

const { Text } = Typography;

interface Props {
  report: ReportItem;
  reportTypeLabel: string;
}

/** 去除模型中多余的思考过程标签 <think>...</think> */
function stripThinkTags(content: string): string {
  return content.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

const ReportContent: React.FC<Props> = ({ report, reportTypeLabel }) => {
  const cleanContent = stripThinkTags(report.content);

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined style={{ color: '#1677ff', fontSize: 16 }} />
          <Text strong style={{ fontSize: 15 }}>
            {reportTypeLabel}
          </Text>
        </div>
        <Text type="secondary" style={{ fontSize: 13 }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {report.created_at
            ? new Date(report.created_at).toLocaleString('zh-CN')
            : '-'}
        </Text>
      </div>

      <div
        className="report-content"
        style={{
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          padding: '20px 24px',
          background: '#fff',
          lineHeight: 1.8,
        }}
      >
        {cleanContent ? (
          <ReactMarkdown>{cleanContent}</ReactMarkdown>
        ) : (
          <Text type="secondary">（报告内容为空）</Text>
        )}
      </div>
    </div>
  );
};

export default ReportContent;

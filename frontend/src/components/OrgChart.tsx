import React from 'react';
import { Card, Typography, Badge, Tooltip } from 'antd';
import { UserOutlined, CrownOutlined } from '@ant-design/icons';
import type { PersonItem } from '../api';

const { Text } = Typography;

/** 根据职位关键词推断层级 */
function inferLevel(position: string): number {
  const pos = position.toLowerCase();
  if (pos.includes('ceo') || pos.includes('总经理') || pos.includes('创始人') || pos.includes('董事长') || pos.includes('总裁')) return 0;
  if (pos.includes('cfo') || pos.includes('cto') || pos.includes('coo') || pos.includes('cmo') || pos.includes('总监') || pos.includes('vp') || pos.includes('副总裁') || pos.includes('副总经理') || pos.includes('总工程师')) return 1;
  if (pos.includes('经理') || pos.includes('主管') || pos.includes('主任') || pos.includes('部长') || pos.includes('负责人')) return 2;
  return 3;
}

interface Props {
  persons: PersonItem[];
  onPersonClick: (person: PersonItem) => void;
}

const OrgChart: React.FC<Props> = ({ persons, onPersonClick }) => {
  // 按层级分组
  const grouped = persons.reduce<Record<number, PersonItem[]>>((acc, p) => {
    const level = inferLevel(p.position);
    if (!acc[level]) acc[level] = [];
    acc[level].push(p);
    return acc;
  }, {});

  const levels = Object.keys(grouped)
    .map(Number)
    .sort((a, b) => a - b);

  if (persons.length === 0) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: '60px 20px',
          color: '#bfbfbf',
          border: '2px dashed #e8e8e8',
          borderRadius: 12,
        }}
      >
        <UserOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
        <div style={{ fontSize: 15, marginBottom: 8 }}>暂无人员数据</div>
        <Text type="secondary">请点击右上角「新增人员」按钮添加企业核心人员</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px 0' }}>
      {levels.map((level) => (
        <div key={level} style={{ marginBottom: level < levels.length - 1 ? 32 : 0 }}>
          {/* 层级标签 */}
          <div
            style={{
              textAlign: 'center',
              marginBottom: 16,
              color: '#8c8c8c',
              fontSize: 12,
              letterSpacing: 2,
              textTransform: 'uppercase',
            }}
          >
            ═══ {level === 0 ? '决策层' : level === 1 ? '管理层' : level === 2 ? '执行层' : '基础层'} ═══
          </div>

          {/* 连线 */}
          {levels.indexOf(level) > 0 && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                marginBottom: 8,
              }}
            >
              <div
                style={{
                  width: 2,
                  height: 20,
                  background: '#d9d9d9',
                }}
              />
            </div>
          )}

          {/* 该层人员卡片 */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              flexWrap: 'wrap',
              gap: 16,
              padding: '0 20px',
            }}
          >
            {grouped[level].map((person) => (
              <Tooltip key={person.id} title={`点击查看 ${person.name} 的详情与话题分析`}>
                <Card
                  hoverable
                  size="small"
                  onClick={() => onPersonClick(person)}
                  style={{
                    width: 160,
                    borderRadius: 10,
                    border: '1px solid #f0f0f0',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  styles={{
                    body: { padding: '14px 16px', textAlign: 'center' },
                  }}
                >
                  {/* 头像 */}
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: '50%',
                      background: level === 0 ? '#f5222d' : level === 1 ? '#1677ff' : level === 2 ? '#52c41a' : '#8c8c8c',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 10px',
                      position: 'relative',
                      color: '#fff',
                      fontSize: 20,
                      fontWeight: 600,
                    }}
                  >
                    {person.name.charAt(0)}
                    {level === 0 && (
                      <CrownOutlined
                        style={{
                          position: 'absolute',
                          top: -6,
                          right: -6,
                          color: '#ffd700',
                          fontSize: 16,
                        }}
                      />
                    )}
                  </div>

                  {/* 姓名 */}
                  <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>
                    {person.name}
                  </Text>

                  {/* 职位 */}
                  <Text
                    type="secondary"
                    style={{ fontSize: 11, display: 'block', lineHeight: 1.3 }}
                    ellipsis={{ tooltip: person.position }}
                  >
                    {person.position}
                  </Text>
                </Card>
              </Tooltip>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export default OrgChart;

import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { Button, Spin, message, Typography, Space, Modal, Form, Input, Select } from 'antd';
import { PlusOutlined, TeamOutlined } from '@ant-design/icons';
import {
  listPersons,
  createPerson,
  PersonItem,
  PersonCreatePayload,
} from '../api';
import OrgChart from '../components/OrgChart';
import { serializeHobbyTags } from '../utils/hobbies';

const { Title, Text } = Typography;

interface OutletContext {
  companyId: number;
  company: { name: string };
  loadStatus: () => void;
}

const PeopleAnalysis: React.FC = () => {
  const { companyId, loadStatus } = useOutletContext<OutletContext>();
  const navigate = useNavigate();

  const [persons, setPersons] = useState<PersonItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchPersons = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      const data = await listPersons(companyId);
      setPersons(data);
    } catch (e: any) {
      message.error('加载人员列表失败');
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    fetchPersons();
  }, [fetchPersons]);

  const handleAdd = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload: PersonCreatePayload = {
        ...values,
        hobbies: serializeHobbyTags(values.hobbies),
      };
      await createPerson(companyId, payload);
      message.success('新增人员成功');
      form.resetFields();
      setModalOpen(false);
      fetchPersons();
      loadStatus();
    } catch (e: any) {
      if (e.errorFields) return;
      message.error('新增失败: ' + (e.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

  const handlePersonClick = (person: PersonItem) => {
    navigate(`/companies/${companyId}/person/${person.id}`);
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
          <TeamOutlined style={{ fontSize: 22, color: '#722ed1' }} />
          <div>
            <Title level={4} style={{ margin: 0 }}>
              人员分析
            </Title>
            <Text type="secondary">
              企业核心团队组织架构 {persons.length > 0 ? `（共 ${persons.length} 人）` : ''}
            </Text>
          </div>
        </Space>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          新增人员
        </Button>
      </div>

      {/* 组织架构图 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : (
        <OrgChart persons={persons} onPersonClick={handlePersonClick} />
      )}

      {/* 新增人员 Modal */}
      <Modal
        title="新增核心人员"
        open={modalOpen}
        onOk={handleAdd}
        onCancel={() => {
          form.resetFields();
          setModalOpen(false);
        }}
        confirmLoading={submitting}
        destroyOnClose
        width={600}
      >
        <Form form={form} layout="vertical" autoComplete="off" initialValues={{ hobbies: [] }}>
          <Form.Item
            name="name"
            label="姓名"
            rules={[{ required: true, message: '请输入姓名' }]}
          >
            <Input placeholder="请输入姓名" maxLength={100} />
          </Form.Item>
          <Form.Item
            name="position"
            label="职位"
            rules={[{ required: true, message: '请输入职位' }]}
          >
            <Input placeholder="请输入职位名称" maxLength={200} />
          </Form.Item>
          <Form.Item name="joined_date" label="入职时间">
            <Input placeholder="如 2024-03" maxLength={20} />
          </Form.Item>
          <Form.Item name="background" label="背景描述">
            <Input.TextArea rows={3} placeholder="教育背景、工作履历等" />
          </Form.Item>
          <Form.Item name="public_links" label="公开链接">
            <Input placeholder="LinkedIn / 微博 / 公司官网等 URL" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} placeholder="内部备注" />
          </Form.Item>
          <Form.Item
            name="hobbies"
            label="兴趣爱好"
            extra="输入后按回车添加标签。「企业」为系统自带新闻标签，无需录入"
          >
            <Select
              mode="tags"
              style={{ width: '100%' }}
              placeholder="如：高尔夫、跑步、摄影"
              tokenSeparators={[',', '，', '、', ';', '；']}
              maxTagCount={20}
              open={false}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PeopleAnalysis;

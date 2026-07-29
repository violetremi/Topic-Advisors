import React, { useEffect, useState, useCallback } from 'react';
import { Table, Button, Modal, Form, Input, Space, message, Popconfirm, Select, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons';
import { listPersons, createPerson, deletePerson, PersonItem, PersonCreatePayload } from '../api';
import { parseHobbyTags, serializeHobbyTags } from '../utils/hobbies';

interface Props {
  companyId: number;
  onChange?: (count: number) => void;
}

const PersonTable: React.FC<Props> = ({ companyId, onChange }) => {
  const [persons, setPersons] = useState<PersonItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchPersons = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPersons(companyId);
      setPersons(data);
      onChange?.(data.length);
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
    } catch (e: any) {
      if (e.errorFields) return;
      message.error('新增失败: ' + (e.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (personId: number) => {
    try {
      await deletePerson(companyId, personId);
      message.success('删除成功');
      fetchPersons();
    } catch (e: any) {
      message.error('删除失败: ' + (e.message || ''));
    }
  };

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name', width: 120 },
    { title: '职位', dataIndex: 'position', key: 'position', width: 180, ellipsis: true },
    {
      title: '入职时间',
      dataIndex: 'joined_date',
      key: 'joined_date',
      width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: '背景描述',
      dataIndex: 'background',
      key: 'background',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '兴趣爱好',
      dataIndex: 'hobbies',
      key: 'hobbies',
      width: 180,
      render: (v: string) => {
        const tags = parseHobbyTags(v);
        if (!tags.length) return '-';
        return (
          <Space size={[4, 4]} wrap>
            {tags.map((t) => (
              <Tag key={t} color="purple">
                {t}
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: '公开链接',
      dataIndex: 'public_links',
      key: 'public_links',
      width: 200,
      ellipsis: true,
      render: (v: string) =>
        v ? (
          <a href={v} target="_blank" rel="noopener noreferrer">
            {v.slice(0, 30)}...
          </a>
        ) : (
          '-'
        ),
    },
    { title: '备注', dataIndex: 'notes', key: 'notes', ellipsis: true, render: (v: string) => v || '-' },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: PersonItem) => (
        <Popconfirm
          title="确定删除该人员？"
          onConfirm={() => handleDelete(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 15 }}>
          <UserOutlined style={{ marginRight: 6 }} />
          核心人员列表
        </span>
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新增人员
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={persons}
        loading={loading}
        size="small"
        pagination={false}
      />

      {/* 新增人员弹窗 */}
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

export default PersonTable;

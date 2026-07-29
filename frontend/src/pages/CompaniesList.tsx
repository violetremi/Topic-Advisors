import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Space, message, Tag } from 'antd';
import { PlusOutlined, RightCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listCompanies, countCompanies, CompanyItem } from '../api';
import CompanyModal from '../components/CompanyModal';

const CompaniesList: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<CompanyItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [companies, countRes] = await Promise.all([
        listCompanies(page, 20),
        countCompanies(),
      ]);
      setData(companies);
      setTotal(countRes.total);
    } catch (e: any) {
      message.error('加载企业列表失败: ' + (e.message || ''));
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const columns = [
    {
      title: '企业编号',
      dataIndex: 'company_code',
      key: 'company_code',
      width: 200,
    },
    {
      title: '企业名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '统一社会信用代码',
      dataIndex: 'credit_code',
      key: 'credit_code',
      width: 200,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string | null) =>
        v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: CompanyItem) => (
        <Button
          type="primary"
          size="small"
          icon={<RightCircleOutlined />}
          onClick={() => navigate(`/companies/${record.id}`)}
        >
          进入
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0 }}>企业列表</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新增企业
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 家企业`,
        }}
      />

      <CompanyModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          setModalOpen(false);
          fetchData();
        }}
      />
    </div>
  );
};

export default CompaniesList;

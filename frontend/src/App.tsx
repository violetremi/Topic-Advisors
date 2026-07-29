import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Button, Popconfirm, Space } from 'antd';
import {
  SafetyOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import CompaniesList from './pages/CompaniesList';
import CompanyLayout from './pages/CompanyLayout';
import IndustryDetail from './pages/IndustryDetail';
import CompanyAnalysisDetail from './pages/CompanyAnalysisDetail';
import PeopleAnalysis from './pages/PeopleAnalysis';
import PersonDetail from './pages/PersonDetail';
import SummaryAnalysis from './pages/SummaryAnalysis';
import SystemSettings from './pages/SystemSettings';
import Login from './pages/Login';
import { useAuth } from './context/AuthContext';

const { Sider, Header, Content } = Layout;
const { Text } = Typography;

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { username, logout } = useAuth();

  // 根据当前路径确定选中的菜单项
  const selectedKey = location.pathname.startsWith('/companies')
    ? '/companies'
    : location.pathname;

  const menuItems = [
    {
      key: '/companies',
      icon: <SafetyOutlined />,
      label: '密探管理',
    },
    {
      key: '/system',
      icon: <SettingOutlined />,
      label: '系统管理',
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 深色侧边栏 */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffd700',
            fontSize: collapsed ? 16 : 20,
            fontWeight: 700,
            letterSpacing: 2,
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          {collapsed ? '密' : '🕵️ 大内密探'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 220, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            borderBottom: '1px solid #f0f0f0',
            height: 64,
            position: 'sticky',
            top: 0,
            zIndex: 99,
          }}
        >
          {React.createElement(collapsed ? MenuUnfoldOutlined : MenuFoldOutlined, {
            style: { fontSize: 18, cursor: 'pointer' },
            onClick: () => setCollapsed(!collapsed),
          })}
          <Text strong style={{ marginLeft: 16, fontSize: 16 }}>
            企业情报分析系统
          </Text>
          <Space style={{ marginLeft: 'auto' }} size="middle">
            <Text type="secondary">
              <UserOutlined /> {username}
            </Text>
            <Popconfirm
              title="退出登录"
              description="将以当前用户名登出，数据不会删除。"
              okText="退出"
              cancelText="取消"
              onConfirm={logout}
            >
              <Button size="small" icon={<LogoutOutlined />}>退出</Button>
            </Popconfirm>
          </Space>
        </Header>
        <Content style={{ background: '#fff', minHeight: 'calc(100vh - 64px)' }}>
          <Routes>
            <Route path="/" element={<CompaniesList />} />
            <Route path="/companies" element={<CompaniesList />} />
            <Route path="/companies/:id" element={<CompanyLayout />}>
              <Route index element={<IndustryDetail />} />
              <Route path="industry" element={<IndustryDetail />} />
              <Route path="company" element={<CompanyAnalysisDetail />} />
              <Route path="people" element={<PeopleAnalysis />} />
              <Route path="summary" element={<SummaryAnalysis />} />
            </Route>
            <Route path="/companies/:id/person/:personId" element={<PersonDetail />} />
            <Route path="/system" element={<SystemSettings />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => {
  const { username } = useAuth();
  return (
    <BrowserRouter>
      {username ? <AppLayout /> : <Login />}
    </BrowserRouter>
  );
};

export default App;

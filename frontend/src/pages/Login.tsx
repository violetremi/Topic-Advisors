/** 登录页：仅录入唯一用户名即可登录。
 *  - 用户名不存在 -> 后端自动创建账号
 *  - 用户名已存在 -> 直接进入其账号（数据隔离）
 */
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, Input, Button, Typography, message } from 'antd';
import { SafetyOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!username.trim()) {
      message.warning('请输入用户名');
      return;
    }
    setLoading(true);
    try {
      await login(username);
      message.success(`欢迎，${username.trim()}`);
    } catch (e) {
      message.error((e as Error).message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1f1c2c 0%, #2c3e50 100%)',
        padding: 16,
      }}
    >
      <Card
        style={{ width: 380, maxWidth: '100%', boxShadow: '0 8px 30px rgba(0,0,0,0.4)' }}
        variant="borderless"
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <SafetyOutlined style={{ fontSize: 40, color: '#ffd700' }} />
          <Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>
            🕵️ 大内密探
          </Title>
          <Text type="secondary">企业情报分析系统</Text>
        </div>

        <Input
          size="large"
          placeholder="请输入用户名"
          value={username}
          maxLength={64}
          autoFocus
          onPressEnter={handleLogin}
          onChange={(e) => setUsername(e.target.value)}
          style={{ marginBottom: 16 }}
        />

        <Button
          type="primary"
          size="large"
          block
          loading={loading}
          onClick={handleLogin}
        >
          登 录
        </Button>

        <Text
          type="secondary"
          style={{ display: 'block', textAlign: 'center', marginTop: 16, fontSize: 12 }}
        >
          用户名即账号，无需密码。同一用户名将进入同一工作区。
        </Text>
      </Card>
    </div>
  );
};

export default Login;

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  message,
  Spin,
  Typography,
  Divider,
  Descriptions,
  Tag,
  Select,
} from 'antd';
import {
  SaveOutlined,
  ApiOutlined,
  KeyOutlined,
  RobotOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { getSettings, updateSettings } from '../api';

const { Title, Paragraph, Text } = Typography;

const SystemSettings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle');

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSettings();
      const kv: Record<string, string> = {};
      data.items.forEach((item) => {
        kv[item.key] = item.value;
      });
      form.setFieldsValue(kv);
    } catch (e: any) {
      message.error('加载配置失败: ' + (e.message || ''));
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const items = Object.entries(values).map(([key, value]) => ({
        key,
        value: String(value),
      }));
      await updateSettings(items);
      message.success('配置已保存');
    } catch (e: any) {
      if (e.errorFields) return;
      message.error('保存失败: ' + (e.message || ''));
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    try {
      const values = form.getFieldsValue();
      const baseUrl = values.llm_base_url || '';
      const apiKey = values.llm_api_key || '';
      const model = values.llm_model || '';

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (apiKey) {
        headers['Authorization'] = 'Bearer ' + apiKey;
      }

      const res = await fetch(baseUrl.replace(/\/+$/, '') + '/chat/completions', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model,
          messages: [{ role: 'user', content: 'ping' }],
          max_tokens: 5,
        }),
      });

      if (res.ok) {
        setTestStatus('ok');
        message.success('模型连接测试成功');
      } else {
        const body = await res.json().catch(() => ({}));
        setTestStatus('fail');
        message.error('模型返回错误: ' + (body.error?.message || res.statusText));
      }
    } catch (e: any) {
      setTestStatus('fail');
      message.error('连接失败: ' + (e.message || ''));
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Title level={4} style={{ marginBottom: 8 }}>
        系统配置
      </Title>
      <Paragraph type="secondary" style={{ marginBottom: 24 }}>
        配置 AI 大模型参数，保存后即时生效，无需重启服务。
      </Paragraph>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : (
        <Form form={form} layout="vertical" autoComplete="off">
          {/* AI 大模型配置 */}
          <Card
            title={
              <span>
                <RobotOutlined style={{ marginRight: 8 }} />
                AI 大模型配置
              </span>
            }
            style={{ marginBottom: 20 }}
          >
            <Form.Item
              name="llm_base_url"
              label="API 接口地址"
              rules={[{ required: true, message: '请输入 API 地址' }]}
              extra="例如 http://127.0.0.1:1234/v1"
            >
              <Input prefix={<ApiOutlined />} placeholder="http://127.0.0.1:1234/v1" />
            </Form.Item>

            <Form.Item
              name="llm_api_key"
              label="API Key"
              extra="如果模型无需鉴权可留空"
            >
              <Input.Password prefix={<KeyOutlined />} placeholder="sk-..." />
            </Form.Item>

            <Form.Item
              name="llm_model"
              label="模型名称"
              rules={[{ required: true, message: '请输入模型名称' }]}
              extra="例如 gpt-4o、qwen2.5:7b、deepseek-chat 等"
            >
              <Input
                prefix={<RobotOutlined />}
                placeholder="gpt-4o"
              />
            </Form.Item>

            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <Button
                icon={<CheckCircleOutlined />}
                onClick={handleTestConnection}
                loading={testStatus === 'testing'}
                type="default"
              >
                {testStatus === 'testing' ? '测试中...' : '测试连接'}
              </Button>

              {testStatus === 'ok' && (
                <Tag color="success" icon={<CheckCircleOutlined />}>
                  连接成功
                </Tag>
              )}
              {testStatus === 'fail' && (
                <Tag color="error" icon={<CloseCircleOutlined />}>
                  连接失败
                </Tag>
              )}
            </div>
          </Card>

          {/* 搜索引擎配置 */}
          <Card
            title={
              <span>
                <GlobalOutlined style={{ marginRight: 8 }} />
                联网搜索引擎配置
              </span>
            }
            style={{ marginBottom: 20 }}
          >
            <Form.Item
              name="search_provider"
              label="搜索引擎"
              extra={
                <span>
                  国内推荐 Tavily/Brave（需 API Key）；DuckDuckGo 免费但经常超时失败。
                  <br />
                  Tavily 申请: https://tavily.com/
                  <br />
                  Brave 申请: https://api.search.brave.com/ （免费 2000 次/月）
                  <br />
                  Bing 申请: https://www.microsoft.com/en-us/bing/apis/bing-web-search-api
                </span>
              }
            >
              <Select>
                <Select.Option value="tavily">🔎 Tavily（推荐，需 API Key）</Select.Option>
                <Select.Option value="brave">🦁 Brave Search（需 API Key）</Select.Option>
                <Select.Option value="bing">🔍 Bing Web Search（需 API Key）</Select.Option>
                <Select.Option value="duckduckgo">🦆 DuckDuckGo（免费，国内不稳定）</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item
              noStyle
              shouldUpdate={(prev, cur) => prev.search_provider !== cur.search_provider}
            >
              {({ getFieldValue }) => {
                const provider = getFieldValue('search_provider');
                if (provider === 'duckduckgo') return null;
                const labelMap: Record<string, string> = {
                  tavily: 'Tavily',
                  brave: 'Brave',
                  bing: 'Bing',
                };
                const label = labelMap[provider] || provider;
                return (
                  <Form.Item
                    name="search_api_key"
                    label={`${label} API Key`}
                    rules={[{ required: true, message: `请输入 ${label} API Key` }]}
                  >
                    <Input.Password
                      prefix={<KeyOutlined />}
                      placeholder={`输入 ${label} API Key`}
                    />
                  </Form.Item>
                );
              }}
            </Form.Item>
          </Card>

          <Divider />

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              loading={saving}
              size="large"
            >
              保存配置
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchSettings}
              style={{ marginLeft: 12 }}
              size="large"
            >
              重置
            </Button>
          </div>
        </Form>
      )}
    </div>
  );
};

export default SystemSettings;

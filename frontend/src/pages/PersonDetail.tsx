import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Spin,
  message,
  Typography,
  Space,
  Card,
  Tag,
  Empty,
  Descriptions,
  Alert,
  Tabs,
  Select,
  Modal,
} from 'antd';
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  CheckCircleFilled,
  BulbOutlined,
  SearchOutlined,
  EditOutlined,
  BankOutlined,
} from '@ant-design/icons';
import {
  getCompany,
  listPersons,
  getTopicAnalysis,
  createTopicAnalysis,
  getCachedPersonHobbyNews,
  getPersonNews,
  updatePerson,
  CompanyItem,
  PersonItem,
  TopicAnalysisItem,
  HobbyNewsGroup,
} from '../api';
import ReportContent from '../components/ReportTimeline';
import NewsTimeline from '../components/NewsTimeline';
import { COMPANY_HOBBY_TAB, parseHobbyTags, serializeHobbyTags } from '../utils/hobbies';

const { Title, Text } = Typography;

const PersonDetail: React.FC = () => {
  const { id, personId } = useParams<{ id: string; personId: string }>();
  const navigate = useNavigate();
  const companyId = Number(id);
  const pid = Number(personId);

  const [company, setCompany] = useState<CompanyItem | null>(null);
  const [person, setPerson] = useState<PersonItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState<TopicAnalysisItem | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  // ── 兴趣 / 企业新闻（按标签分组）──
  const [hobbyGroups, setHobbyGroups] = useState<HobbyNewsGroup[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsSearched, setNewsSearched] = useState(false);
  const [activeHobby, setActiveHobby] = useState<string>(COMPANY_HOBBY_TAB);

  // ── 编辑兴趣爱好 ──
  const [editOpen, setEditOpen] = useState(false);
  const [editTags, setEditTags] = useState<string[]>([]);
  const [savingHobbies, setSavingHobbies] = useState(false);

  const hobbyTags = useMemo(() => parseHobbyTags(person?.hobbies), [person?.hobbies]);

  const displayGroups: HobbyNewsGroup[] = useMemo(() => {
    if (hobbyGroups.length) return hobbyGroups;
    return [
      {
        hobby: COMPANY_HOBBY_TAB,
        items: [],
        ai_filtered: false,
        message: '',
        kind: 'company',
      },
      ...hobbyTags.map((h) => ({
        hobby: h,
        items: [] as HobbyNewsGroup['items'],
        ai_filtered: false,
        message: '',
        kind: 'hobby' as const,
      })),
    ];
  }, [hobbyGroups, hobbyTags]);

  // Load cached hobby news on mount
  useEffect(() => {
    if (!companyId || !pid) return;
    getCachedPersonHobbyNews(companyId, pid)
      .then((resp) => {
        if (resp.groups.length) {
          setHobbyGroups(resp.groups);
          const hasNews = resp.groups.some((g) => g.items.length > 0);
          if (hasNews) setNewsSearched(true);
          const firstWithNews =
            resp.groups.find((g) => g.items.length > 0)?.hobby
            || resp.groups[0]?.hobby
            || COMPANY_HOBBY_TAB;
          setActiveHobby(firstWithNews);
        }
      })
      .catch(() => {/* silent */});
  }, [companyId, pid]);

  // Load company and person info
  useEffect(() => {
    if (!companyId || !pid) return;
    setLoading(true);

    Promise.all([
      getCompany(companyId),
      listPersons(companyId),
    ])
      .then(([comp, persons]) => {
        setCompany(comp);
        const found = persons.find((p) => p.id === pid);
        setPerson(found || null);
      })
      .catch((e) => message.error('加载信息失败: ' + (e.message || '')))
      .finally(() => setLoading(false));
  }, [companyId, pid]);

  // Sync active tab when groups change
  useEffect(() => {
    const keys = displayGroups.map((g) => g.hobby);
    if (!keys.length) return;
    if (!activeHobby || !keys.includes(activeHobby)) {
      setActiveHobby(keys[0]);
    }
  }, [displayGroups, activeHobby]);

  // Load existing analysis
  useEffect(() => {
    if (!companyId || !pid) return;
    setAnalysisLoading(true);
    getTopicAnalysis(companyId, pid)
      .then((result) => {
        if (result.content) setAnalysis(result);
      })
      .catch(() => {/* silent */})
      .finally(() => setAnalysisLoading(false));
  }, [companyId, pid]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await createTopicAnalysis(companyId, pid);
      setAnalysis(result);
      message.success('话题分析生成完成');
    } catch (e: any) {
      message.error(e.message || '生成失败');
    } finally {
      setGenerating(false);
    }
  };

  const openEditHobbies = () => {
    setEditTags(hobbyTags);
    setEditOpen(true);
  };

  const handleSaveHobbies = async () => {
    const cleaned = parseHobbyTags(editTags);
    if (cleaned.some((t) => t === COMPANY_HOBBY_TAB)) {
      message.warning(`「${COMPANY_HOBBY_TAB}」为系统自带标签，不能作为兴趣录入`);
      return;
    }
    setSavingHobbies(true);
    try {
      const updated = await updatePerson(companyId, pid, {
        hobbies: serializeHobbyTags(cleaned),
      });
      setPerson(updated);
      setEditOpen(false);
      // 同步 Tab：保留企业组，按新兴趣标签重建兴趣组（复用已有同名结果）
      setHobbyGroups((prev) => {
        const companyGroup =
          prev.find((g) => g.kind === 'company' || g.hobby === COMPANY_HOBBY_TAB) || {
            hobby: COMPANY_HOBBY_TAB,
            items: [],
            ai_filtered: false,
            message: '',
            kind: 'company',
          };
        const hobbyMap = new Map(
          prev.filter((g) => g.kind !== 'company' && g.hobby !== COMPANY_HOBBY_TAB).map((g) => [g.hobby, g])
        );
        return [
          companyGroup,
          ...cleaned.map(
            (h) =>
              hobbyMap.get(h) || {
                hobby: h,
                items: [],
                ai_filtered: false,
                message: '',
                kind: 'hobby',
              }
          ),
        ];
      });
      message.success('兴趣爱好已更新');
    } catch (e: any) {
      message.error('保存失败: ' + (e.message || ''));
    } finally {
      setSavingHobbies(false);
    }
  };

  const handleSearchNews = async () => {
    setNewsLoading(true);
    try {
      const resp = await getPersonNews(companyId, pid);
      setHobbyGroups(resp.groups);
      setNewsSearched(true);
      const prefer =
        resp.groups.find((g) => g.items.length > 0)?.hobby
        || resp.groups[0]?.hobby
        || COMPANY_HOBBY_TAB;
      setActiveHobby(prefer);
      if (resp.message) {
        message.success(resp.message);
      } else {
        const total = resp.groups.reduce((s, g) => s + g.items.length, 0);
        message.info(total > 0 ? `共找到 ${total} 条相关新闻` : '暂无匹配的新闻');
      }
    } catch (e: any) {
      message.error('搜索新闻失败: ' + (e.message || ''));
    } finally {
      setNewsLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!person) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Empty description="人员不存在" />
        <Button onClick={() => navigate(`/companies/${companyId}/people`)} style={{ marginTop: 16 }}>
          返回人员分析
        </Button>
      </div>
    );
  }

  const tabItems = displayGroups.map((g) => {
    const isCompany = g.kind === 'company' || g.hobby === COMPANY_HOBBY_TAB;
    return {
      key: g.hobby,
      label: (
        <span>
          {isCompany ? <BankOutlined style={{ marginRight: 4 }} /> : null}
          {g.hobby}
          {g.items.length > 0 ? (
            <Tag color={isCompany ? 'blue' : 'purple'} style={{ marginLeft: 6 }}>
              {g.items.length}
            </Tag>
          ) : null}
        </span>
      ),
      children: (
        <NewsTimeline
          news={g.items}
          loading={newsLoading}
          title={isCompany ? `${person.name} · 企业相关新闻` : `${g.hobby} 兴趣新闻`}
        />
      ),
    };
  });

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(`/companies/${companyId}/people`)}
        style={{ marginBottom: 16, padding: 0 }}
      >
        返回人员分析
      </Button>

      <Card
        style={{
          borderRadius: 12,
          marginBottom: 20,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        }}
        styles={{ body: { padding: 24 } }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: '#722ed1',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: 28,
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            {person.name.charAt(0)}
          </div>

          <div style={{ flex: 1 }}>
            <Title level={4} style={{ margin: 0, marginBottom: 4 }}>
              {person.name}
              <Tag style={{ marginLeft: 8, verticalAlign: 'middle' }} color="purple">
                {person.position}
              </Tag>
              {company?.name ? (
                <Tag style={{ marginLeft: 4, verticalAlign: 'middle' }} color="blue">
                  {company.name}
                </Tag>
              ) : null}
            </Title>
            <Descriptions size="small" column={2} style={{ marginTop: 12 }}>
              {person.joined_date && (
                <Descriptions.Item label="入职时间">{person.joined_date}</Descriptions.Item>
              )}
              <Descriptions.Item label="兴趣爱好" span={2}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
                  {hobbyTags.length ? (
                    <Space size={[6, 6]} wrap>
                      {hobbyTags.map((t) => (
                        <Tag key={t} color="geekblue">
                          {t}
                        </Tag>
                      ))}
                    </Space>
                  ) : (
                    <Text type="secondary">未设置兴趣标签</Text>
                  )}
                  <Button type="link" size="small" icon={<EditOutlined />} onClick={openEditHobbies}>
                    编辑
                  </Button>
                </div>
              </Descriptions.Item>
              {person.background && (
                <Descriptions.Item label="背景描述" span={2}>
                  {person.background}
                </Descriptions.Item>
              )}
              {person.public_links && (
                <Descriptions.Item label="公开链接" span={2}>
                  <a href={person.public_links} target="_blank" rel="noopener noreferrer">
                    {person.public_links.slice(0, 50)}...
                  </a>
                </Descriptions.Item>
              )}
              {person.notes && (
                <Descriptions.Item label="备注" span={2}>
                  {person.notes}
                </Descriptions.Item>
              )}
            </Descriptions>
          </div>
        </div>
      </Card>

      {/* 话题分析区域 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Space size={8}>
          <BulbOutlined style={{ fontSize: 20, color: '#fa8c16' }} />
          <Title level={5} style={{ margin: 0 }}>
            话题分析
          </Title>
          {analysis && (
            <Tag icon={<CheckCircleFilled />} color="success">
              已生成
            </Tag>
          )}
        </Space>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={generating}
          onClick={handleGenerate}
        >
          {generating ? '生成中…' : analysis ? '重新生成' : '生成话题分析'}
        </Button>
      </div>

      {analysisLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : analysis ? (
        <Card
          style={{
            borderRadius: 10,
            border: '1px solid #f0f0f0',
            marginBottom: 24,
          }}
          styles={{ body: { padding: '20px 24px' } }}
        >
          <ReportContent report={analysis as any} reportTypeLabel="话题分析" />
        </Card>
      ) : (
        <div
          style={{
            textAlign: 'center',
            padding: 60,
            background: '#fafafa',
            borderRadius: 10,
            border: '1px dashed #d9d9d9',
            marginBottom: 24,
          }}
        >
          <Empty description="暂无话题分析" />
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            点击上方「生成话题分析」按钮，AI 将根据该人员的背景和兴趣爱好生成商业及兴趣话题
          </Text>
        </div>
      )}

      {/* ── 企业 + 兴趣标签新闻 ── */}
      <div style={{ marginTop: 32 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <Title level={5} style={{ margin: 0 }}>
            <SearchOutlined style={{ marginRight: 8, color: '#722ed1' }} />
            {person.name} 相关新闻
          </Title>
          <Space>
            <Button icon={<EditOutlined />} onClick={openEditHobbies}>
              编辑兴趣
            </Button>
            <Button icon={<SearchOutlined />} loading={newsLoading} onClick={handleSearchNews}>
              {newsLoading ? '搜索筛选中…' : newsSearched ? '重新搜索' : '搜索新闻'}
            </Button>
          </Space>
        </div>

        {!newsSearched ? (
          <Alert
            message={
              hobbyTags.length
                ? `将搜索「企业」相关新闻，以及兴趣标签（${hobbyTags.join('、')}）的纯兴趣新闻；兴趣过滤不带企业关键词`
                : '可先编辑兴趣标签。即使没有兴趣，也可搜索该人员的「企业」相关新闻'
            }
            type="info"
            showIcon
            style={{ borderRadius: 8, marginBottom: 16 }}
          />
        ) : null}

        <Tabs
          activeKey={activeHobby || COMPANY_HOBBY_TAB}
          onChange={setActiveHobby}
          items={tabItems}
          style={{ marginBottom: 24 }}
        />
      </div>

      <Modal
        title="编辑兴趣爱好"
        open={editOpen}
        onOk={handleSaveHobbies}
        onCancel={() => setEditOpen(false)}
        confirmLoading={savingHobbies}
        okText="保存"
        destroyOnClose
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          输入后回车添加标签；可删除已有标签。「{COMPANY_HOBBY_TAB}」为企业自带标签，无需录入。
        </Text>
        <Select
          mode="tags"
          style={{ width: '100%' }}
          value={editTags}
          onChange={(vals) => setEditTags(parseHobbyTags(vals as string[]))}
          placeholder="如：高尔夫、跑步、摄影"
          tokenSeparators={[',', '，', '、', ';', '；']}
          open={false}
        />
      </Modal>
    </div>
  );
};

export default PersonDetail;

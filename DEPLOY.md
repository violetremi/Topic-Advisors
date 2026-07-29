# 部署到 Render（免费 · 一个域名直接访问）

本项目已改造为「后端同源托管前端」的单容器形态，配合 `Dockerfile` 可直接部署到 **Render 免费 Web Service（Docker）**。部署后获得一个 `https://<服务名>.onrender.com` 域名，输入即可访问，无需本地安装任何环境。

> 备注：原计划用 Hugging Face Spaces，但 HF 自 2026-07 起把 Docker Space 锁进付费墙（需 PRO $9/月），免费个人账号无法创建。故改用同样免费的 Render。

---

## 已完成的改造

| 文件 | 改动 |
|------|------|
| `backend/main.py` | 生产环境由 FastAPI 直接托管 `frontend/dist`（含 SPA 兜底路由）；CORS 放宽 |
| `Dockerfile` | 多阶段构建：Node 打包前端 → Python 运行后端，监听 `$PORT`（`0.0.0.0`） |
| `.dockerignore` | 排除 `node_modules`/`.venv`/`.env`/`*.db` 等，加速构建 |
| Git | 已初始化（默认分支 `main`），已忽略大目录与密钥 |

> **数据说明**：Render 免费档磁盘是**临时**的——每次重新部署或容器重启会重置，SQLite 数据会清空。把模型配置写进 Render 的环境变量即可在重启后依然生效；业务数据如需持久化，见文末「外部 Postgres」一节。

---

## 部署步骤

### 1. 代码已在 GitHub
仓库：`https://github.com/violetremi/Topic-Advisors.git`（分支 `main`）。
若需重新推送：
```bash
git push -u origin main
```

### 2. 创建 Render Web Service
1. 打开 https://dashboard.render.com → 用 GitHub 登录注册（**免信用卡**）
2. 右上角 **New +** → **Web Service**
3. **Connect a repository** → 授权 GitHub → 选中 `violetremi/Topic-Advisors`
4. **Environment**：选 **Docker**（关键：不要选 Node/Python 等.buildpack）
5. **Branch**：`main`
6. **Instance Type**：选 **Free**（免费档）
7. **Health Check Path**（可选，推荐）：填 `/api/health`
8. 点 **Create Web Service**

Render 会自动拉代码、按 `Dockerfile` 构建镜像并启动，分配 `https://<服务名>.onrender.com`。构建约 2–4 分钟，可在 **Logs** 标签实时查看。

### 3. 配置模型环境变量（Environment Variables）
在 Service 页面 → **Environment** 标签 → **Add Environment Variable**，添加：

| Key | Value 示例 | 说明 |
|-----|-----------|------|
| `OPENAI_API_KEY` | `sk-xxx` | 云端模型 API Key |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | 模型接口地址（**服务器无本地模型，务必填云端**，如 DeepSeek / OpenAI / 通义） |
| `LLM_MODEL` | `deepseek-chat` | 模型名称 |
| `EMBED_MODEL`（可选） | `text-embedding-3-small` | 若系统用到向量检索 / embedding，需配云端 embedding，否则该部分会失败 |

> 变量名与后端 `backend/config/settings.py` 一一对应：
> `openai_api_key` / `openai_base_url` / `llm_model` / `embed_model`（大写即为环境变量名）。
> 添加后 Render 会自动重新部署使配置生效。

### 4. 访问
部署完成后，浏览器打开 `https://<服务名>.onrender.com` 即可使用。
首次进入左侧菜单 **系统管理**，确认模型配置已生效（页面内也可改）。

---

## 免费档注意事项

- **休眠冷启动**：15 分钟无访问会自动休眠，下次打开需等待约 **30–50 秒** 冷启动。
  - 想保持常驻：用 [UptimeRobot](https://uptimerobot.com) 免费版每 14 分钟 ping 一次 `https://<服务名>.onrender.com/api/health` 即可（免费）。
- **临时磁盘**：容器重启 / 重新部署时 SQLite 数据清空；模型配置走环境变量不受影响。
- **每月额度**：免费档 750 小时/月，单服务常开足够；超量会暂停，下月恢复。

## 数据持久化（可选）：外部免费 Postgres
若希望数据长期保存，可改用 Render 提供的 **PostgreSQL**（免费实例）：
1. Render 控制台新建一个 **PostgreSQL**（选 Free 档），记下连接串 `postgresql://...`
2. 在本 Service 的 Environment 中加变量 `DATABASE_URL=<连接串>`
3. 后端 `settings.py` 已支持 `database_url`，会自动改用 Postgres 存储
4. 前置：需在 `backend/requirements.txt` 增加 `asyncpg` 驱动（如没有则执行 `pip install asyncpg` 并写入 requirements.txt，重新推送）

## 本地开发不受影响
- 本地仍可用 `start.bat` / `start.sh` 一键启动（前端走 vite dev server，后端不触发静态托管分支）。
- 仅当存在 `frontend/dist` 时，后端才会托管前端；开发模式无需打包。

## 常见问题
- **构建失败**：多半是 `npm run build` 出错。本地用 `cd frontend && npm run build` 复现，修好后再推。
- **页面打不开 / 502**：看 Render 的 **Logs** 标签排查；确认环境变量已填且 Service 已重新部署。
- **想换模型**：页面内「系统管理」直接改，或改环境变量后重新部署。
- **彻底删除**：在 Render Service 页面 → **Settings → Delete Service** 即可，GitHub 仓库不受影响。

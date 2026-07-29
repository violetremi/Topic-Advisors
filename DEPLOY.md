# 部署到 Hugging Face Spaces（免费 · 一个域名直接访问）

本项目已改造为「后端同源托管前端」的单容器形态，配合 Dockerfile 可直接部署到 Hugging Face Spaces 免费档，部署后获得一个 `https://<用户名>-<空间名>.hf.space` 域名，输入即可访问。

---

## 已完成的改造

| 文件 | 改动 |
|------|------|
| `backend/main.py` | 生产环境由 FastAPI 直接托管 `frontend/dist`（含 SPA 兜底路由）；CORS 放宽 |
| `Dockerfile` | 多阶段构建：Node 打包前端 → Python 运行后端，监听 `$PORT` |
| `.dockerignore` | 排除 `node_modules`/`.venv`/`.env`/`*.db` 等，加速构建 |
| Git | 已初始化（默认分支 `main`），已忽略大目录与密钥 |

> 数据说明：Hugging Face Spaces 提供 **50GB 持久化磁盘**，SQLite 数据库文件直接存住，配置与情报数据不会因重启丢失。

---

## 部署步骤

### 1. 推送到 GitHub
```bash
# 在项目根目录执行（替换成你自己的仓库地址）
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 2. 创建 Hugging Face Space
1. 打开 https://huggingface.co/spaces → 右上角 **New Space**
2. **Owner** 选自己，**Space name** 随便取（例如 `intel-agent`）
3. **SDK** 选择 **Docker**（关键：不要选 Gradio/Streamlit）
4. **Space Hardware** 选免费档（CPU basic 即可）
5. 点 **Create Space**

### 3. 关联 GitHub 自动部署
在 Space 页面 → **Settings → Repository** 区域：
- 选择 **Connect a GitHub repository**
- 授权并选中你刚推送的仓库
- 保存后，HF 会自动拉取代码、按 `Dockerfile` 构建并启动

> 也可以手动用 Git 推：Space 页面有 `git clone` 地址，`git remote add hf <地址>` 后 `git push hf main` 即可。

### 4. 配置模型密钥（Secrets）
Space 页面 → **Settings → Variables and Secrets** → **New secret**，添加以下三项（对应原 `.env`）：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_API_KEY` | 云端模型 API Key | `sk-xxx` |
| `OPENAI_BASE_URL` | 模型接口地址（**服务器无本地模型，必须填云端**） | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |

> 保存后 Space 会自动重启使配置生效。

### 5. 访问
构建完成后，浏览器打开 `https://<用户名>-<空间名>.hf.space` 即可使用。
首次进入左侧菜单 **系统管理**，确认模型配置已生效（也可在页面里改）。

---

## 国内访问提示
- 免费档 Space 在 **48 小时无访问后会休眠**，下次打开需等待约 10–30 秒冷启动。
- `*.hf.space` 在国内大多可访问，偶有变慢。如需稳定/自己的域名，可在 Cloudflare 加一层免费 Worker 反向代理（同时解决自定义域名 + 访问加速）。

## 本地开发不受影响
- 本地仍可用 `start.bat` / `start.sh` 一键启动（前端走 vite dev server，后端不触发静态托管分支）。
- 仅当存在 `frontend/dist` 时，后端才会托管前端；开发模式无需打包。

## 常见问题
- **构建失败**：多半是 `npm run build` 出错。本地用 `cd frontend && npm run build` 复现，修好后再推。
- **页面打不开 / 502**：看 Space 的 **Logs** 标签排查；确认 Secrets 已填且 Space 已重启。
- **想换模型**：页面内「系统管理」直接改，或改 Secrets 后重启 Space。

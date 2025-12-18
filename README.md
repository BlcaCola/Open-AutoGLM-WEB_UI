# Open-AutoGLM-WEB_UI

这是一个基于Open-AutoGLM项目创建的轻量级的 Web 前端与相关接口，用于更方便地配置模型、管理设备、实时查看任务日志与手机屏幕预览（开发预览）。以下文档概述了新增功能、关键文件、快速启动方法及已知限制。

---

## 🔧 主要新增/修改内容

- **新增 Web 前端（开发预览）**
  - 后端：`web/server.py`（基于 Flask）提供 REST API 与 SSE 日志流。
  - 前端静态资源：`web/static/index.html`、`web/static/main.js`、`web/static/styles.css`。

- **新接口（摘选）**
  - `GET /api/config`、`POST /api/config` — 模型与前端配置保存
  - `GET /api/devices` — 列出设备
  - `POST /api/connect`、`POST /api/disconnect` — 连接/断开设备
  - `GET /api/screenshot` — 返回当前截图（data:image/png;base64,...）与元信息（width/height/current_app）
  - `POST /api/run`（同步触发）与 `GET /api/run_stream`（SSE，实时日志）
  - `GET /api/apps` — 列出支持的应用

- **实时日志（SSE）**
  - 使用 `/api/run_stream` 提供 Server-Sent Events（SSE）形式的流式日志，前端以 `EventSource` 订阅并实时显示。
  - 引入 `QueueWriter` 逻辑，把 Agent 的 stdout/stderr 同步写入队列并镜像回控制台（使 Windows 下启动的 `*.bat` 窗口也能看到完整日志）。

- **屏幕截图与预览**
  - 前端实现实时或手动刷新截图：默认轮询间隔已调整为 **3 秒**（减轻设备与带宽负担）。
  - 后端返回 `data:image/png;base64,...` 格式，前端直接赋值给 `<img>` 显示。
  - 建议在后端对截图进行 PNG 校验（Pillow）并对损坏图片返回占位图或错误信息（开发提示已记录）。

- **UI/UX 改进**
  - 右侧控制卡（模型配置 / 设备 / 运行任务 / 应用列表）支持 **折叠/展开**，并把折叠状态保存在 `localStorage`。
  - 运行任务区显示完整的实时日志流（SSE），并在任务结束时关闭连接。

- **文档与启动脚本**
  - 在 `README.md` 中增加了 Web UI 的使用简要说明（见下方快速开始）。

---

## 🚀 快速开始（Web UI）

1. 启动：

使用“启动.bat”快速启动

2. 使用 Web UI：

访问 http://127.0.0.1:5000

3. 前端功能：
- 输入并保存模型 `base_url`、`model`、`api_key` 等；
- 列表 / 连接 / 断开设备；
- 在 `运行任务` 中直接输入任务并开始（实时日志会显示在下方）；
- 切换截图实时模式（默认 3 秒刷新）或手动刷新。

> ⚠️ 注意：当前 Web 前端为开发预览。`POST /api/run` 以同步方式触发 Agent（可能会阻塞请求线程）。建议生产环境使用后台任务队列或 websocket 以避免阻塞。

---

## 📁 重要文件一览

| 位置 | 描述 |
|------|------|
| `web/server.py` | Flask 后端，暴露 API 与 SSE 日志流 |
| `web/static/index.html` | 前端页面骨架 |
| `web/static/main.js` | 前端逻辑（API 调用、EventSource、截图轮询、折叠状态） |
| `web/static/styles.css` | 前端样式 |
| `requirements.txt` | 新增 Flask、flask-cors（请确保安装） |

---

## 📝 已知问题与建议

- **截图损坏**：若出现类似 `broken PNG file` 的错误，说明后端返回的 PNG 二进制流可能被截断或被文本污染；建议在后端对图片进行校验（Pillow）并在失败时返回占位图。
- **PowerShell 的 curl 别名问题**：在 Windows 上用 curl 测试 SSE 时请注意 PowerShell 可能将 `curl` 解析为别名，推荐使用浏览器或原生 `curl.exe`。
- **长期运行与可靠性**：当前 `run` 路径为同步实现，生产环境建议改为后台任务队列并通过 SSE/WebSocket 推送日志。
- **其他问题**：关于Open-AutoGLM项目的问题请回到原版页面查询。

---

## 🤝 反馈与贡献

如果你发现 bug 或想要改进：
- 提交 Issue 或 Pull Request 到本仓库；
- 欢迎在 PR 中说明复现步骤、日志片段（注意去敏感信息）以及你建议的改动。

---

## 许可证

遵循项目根目录下的 `LICENSE`。


---



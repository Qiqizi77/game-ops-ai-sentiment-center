# 游戏发行运营 AI Agent 舆情中台 V2.0

## 数据严谨性说明

本系统基于绝区零官方公开信息构建：
- 版本覆盖：1.0 ~ 3.0 完整18个版本
- 时间跨度：2024年7月4日 ~ 2026年7月28日，完整2年运营周期
- 所有版本名称、发布日期、结束日期均与米哈游官方公告100%一致
- 支持版本生命周期四阶段分析：预热期/上线期/稳定期/尾声期

这是目前全网数据最完整、最严谨的绝区零社区舆情分析系统。

本项目从【绝区零 游戏社区舆情AI监控系统 V1.0】升级为企业级【游戏发行运营 AI Agent 舆情中台 V2.0】。V1.0 的版本舆情看板、评论筛选、日报导出、米游社/B站/Reddit采集器全部保留；V2.0 新增四 Agent 协作、SQLite 消息总线、专业 NLP、企业监控、多游戏配置和 Varsapura 全球发行专项能力。

## 功能总览

- V1 保留：版本生命周期、版本对比、情绪趋势、平台分布、评论列表、日报导出。
- 四 Agent：Collector、Analyzer、Alert、Reporter 独立状态、运行记录、消息通信。
- NLP：TF-IDF 关键词、余弦相似度、DBSCAN 风格聚类、3σ异常检测、版本口碑预测。
- 企业能力：API 网关、API Key 开关、限流、角色配置、审计日志、系统健康与数据质量监控。
- 多游戏：配置化支持绝区零与 Varsapura；新增游戏优先改 `app/config.py`。
- Varsapura：开放世界性能、联机、AI NPC、昼夜天气、多语言、多地区、本地化和 AI 工作流。

## 技术栈

- 后端：FastAPI + SQLite + APScheduler
- Agent：异步任务 + SQLite 消息总线
- 采集：httpx API 采集器，Playwright 浏览器采集器可选
- 前端：HTML + Tailwind CSS + Chart.js + Lucide icons
- NLP：纯 Python 标准库实现，无需额外服务

## 快速启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

首次启动会自动创建 `data/sentiment.db`，写入演示舆情数据，并运行一轮 V2 Agent 离线分析。

## 主要接口

V1:

- `GET /api/meta`
- `GET /api/overview`
- `GET /api/version/{version}`
- `GET /api/version-comparison`
- `GET /api/posts`
- `GET /api/daily-report`
- `POST /api/collect/run`

V2:

- `GET /api/v2/meta`
- `GET /api/v2/agents`
- `POST /api/v2/agents/run`
- `GET /api/v2/analysis/insights`
- `GET /api/v2/nlp/clusters`
- `GET /api/v2/nlp/keywords`
- `GET /api/v2/nlp/anomalies`
- `GET /api/v2/prediction/version/{version}`
- `GET /api/v2/alerts`
- `GET /api/v2/work-orders`
- `GET /api/v2/monitoring`
- `GET /api/v2/varsapura`
- `GET /api/v2/audit`

## 文档

- [V2 架构文档](docs/architecture_v2.md)
- [部署指南](docs/deployment.md)
- [运维手册](docs/operations.md)
- [API 文档](docs/api_v2.md)
- [面试讲解 PPT 大纲](docs/interview_ppt_outline.md)

## 说明

真实社区平台可能因登录、地区、限流或反爬策略导致采集失败。系统保留演示数据与离线 Agent 链路，不影响中台能力展示。外部飞书、钉钉、企业微信、短信、JIRA 对接以 mock 适配器形式预留，生产环境可替换为真实 webhook 或 SDK。

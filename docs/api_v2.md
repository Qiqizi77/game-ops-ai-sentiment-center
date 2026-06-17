# V2 API 文档

## Agent

- `GET /api/v2/agents`：Agent 状态与消息总线。
- `POST /api/v2/agents/run`：按 Collector → Analyzer → Alert → Reporter 顺序运行。
- `POST /api/v2/agents/{agent_type}/run`：运行单个 Agent。

## NLP

- `GET /api/v2/analysis/insights`：语义洞察。
- `GET /api/v2/nlp/clusters`：聚类结果。
- `GET /api/v2/nlp/keywords`：TF-IDF 热词和新词。
- `GET /api/v2/nlp/anomalies`：时间序列异常。
- `GET /api/v2/prediction/version/{version}`：版本口碑预测。

## Enterprise

- `GET /api/v2/alerts`：风险预警。
- `GET /api/v2/work-orders`：自动工单。
- `GET /api/v2/reports`：Agent 报告。
- `GET /api/v2/monitoring`：系统健康与数据质量。
- `GET /api/v2/audit`：审计日志。

## Multi-game

- `GET /api/v2/games`：多游戏配置。
- `GET /api/v2/varsapura`：Varsapura 专项配置与工作流。

## 鉴权与审计

默认演示环境关闭强制鉴权，但会记录审计日志。启用后请求头：

```text
X-API-Key: demo-v2-local-key
X-User: alice
X-User-Role: operator
```

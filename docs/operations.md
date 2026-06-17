# 运维手册

## 健康检查

- 应用：`GET /api/health`
- 中台：`GET /api/v2/monitoring`
- Agent：`GET /api/v2/agents`

## 常见操作

运行完整 Agent 链路：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v2/agents/run
```

仅运行预警 Agent：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v2/agents/alert/run
```

查看开放告警：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/alerts?status=open
```

## 故障处理

- Agent `degraded`：查看 `agent_runs.error` 和 `agent_states.last_error`。
- 采集失败：查看 `collector_offsets.last_error`，必要时启用浏览器采集。
- 告警过多：提高 `AGENT_CONFIG["alert"]["level2_cluster_size"]` 或聚类阈值。
- 数据重复率高：检查平台原始 ID 是否稳定，必要时增强 `post_id` 规则。

## 数据清理

演示环境可直接删除：

```powershell
Remove-Item data\sentiment.db
```

下次启动会自动重建表结构与样例数据。

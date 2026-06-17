# 部署指南

## 本地 Demo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 生产部署建议

- 进程：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 数据：SQLite 可直接落盘；高并发生产环境可平滑替换为 PostgreSQL。
- 采集：第一阶段启用 API 采集；浏览器采集器部署在独立节点。
- 鉴权：将 `FEATURE_FLAGS["api_gateway_auth"]` 改为 `True`，通过 `X-API-Key` 访问。
- 定时：APScheduler 已内置，生产环境建议增加进程守护。

## API Key

默认演示 Key：

```text
demo-v2-local-key
```

生产环境请改为环境变量或密钥管理系统。

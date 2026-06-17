from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NAME, BASE_DIR, CATEGORIES, PLATFORM_NAMES
from app.database import fetch_posts, init_db, list_versions
from app.seed import seed_if_empty
from app.services.metrics import daily_report, overview, version_comparison, version_metrics
from app.tasks import run_collection
from app.routes_v2 import router as v2_router
from app.agents.orchestrator import run_agent, run_all_agents


scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()
    scheduler.add_job(run_collection, "interval", hours=6, id="collect_api_posts", replace_existing=True)
    scheduler.add_job(run_agent, "interval", minutes=15, args=["collector"], id="v2_collector_agent", replace_existing=True)
    scheduler.add_job(run_agent, "interval", minutes=10, args=["analyzer"], id="v2_analyzer_agent", replace_existing=True)
    scheduler.add_job(run_agent, "interval", minutes=5, args=["alert"], id="v2_alert_agent", replace_existing=True)
    scheduler.add_job(run_agent, "interval", minutes=60, args=["reporter"], id="v2_reporter_agent", replace_existing=True)
    scheduler.start()
    await run_all_agents(live_collection=False)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title=APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(v2_router)


@app.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "name": APP_NAME}


@app.get("/api/meta")
async def meta() -> dict[str, object]:
    return {
        "app_name": APP_NAME,
        "versions": list_versions(),
        "platforms": PLATFORM_NAMES,
        "categories": list(CATEGORIES.values()),
    }


@app.get("/api/versions")
async def versions() -> list[dict[str, object]]:
    return list_versions()


@app.get("/api/posts")
async def posts(
    version: str | None = None,
    platform: str | None = None,
    category: str | None = None,
    warning_level: int | None = None,
    q: str | None = None,
    range: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 80,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    from app.services.metrics import range_start

    return fetch_posts(
        version=version,
        platform=platform,
        category=category,
        warning_level=warning_level,
        query=q,
        start_date=range_start(range),
        limit=limit,
        offset=offset,
    )


@app.get("/api/overview")
async def overview_api(
    version: str | None = None,
    platform: str | None = None,
    category: str | None = None,
    range: str | None = None,
) -> dict[str, object]:
    return overview(version=version, platform=platform, category=category, range_name=range)


@app.get("/api/version/{version}")
async def version_api(version: str, range: str | None = None) -> dict[str, object]:
    return version_metrics(version, range_name=range)


@app.get("/api/version-comparison")
async def version_comparison_api(
    versions: Annotated[list[str] | None, Query()] = None,
    range: str | None = None,
) -> dict[str, object]:
    return version_comparison(versions=versions, range_name=range)


@app.get("/api/daily-report")
async def daily_report_api(date: str | None = None) -> dict[str, object]:
    return daily_report(date)


@app.get("/api/export/daily-report")
async def daily_report_export(date: str | None = None) -> PlainTextResponse:
    report = daily_report(date)
    filename = f"zzz-sentiment-daily-{report['date']}.md"
    return PlainTextResponse(
        report["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/collect/run")
async def collect_now(
    keyword: str = "绝区零",
    include_browser: bool = False,
) -> dict[str, object]:
    return await run_collection(keyword=keyword, include_browser=include_browser)


@app.get("/api/readme")
async def readme() -> PlainTextResponse:
    readme_path = BASE_DIR / "README.md"
    return PlainTextResponse(readme_path.read_text(encoding="utf-8"))

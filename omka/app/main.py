from contextlib import asynccontextmanager

from fastapi import FastAPI

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.core.scheduler import schedule_daily_job, shutdown_scheduler, start_scheduler
from omka.app.storage.db import init_db
from omka.app.storage.repositories import load_profile_sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OMKA 启动中 | 版本=%s | 环境=%s", settings.app_version, settings.app_env)

    init_db()

    loaded = load_profile_sources()
    if loaded > 0:
        logger.info("从配置文件加载 %d 个数据源", loaded)

    start_scheduler()

    from omka.app.services.daily_job import run_daily_job
    schedule_daily_job(run_daily_job)

    logger.info("OMKA 启动完成 | API=http://%s:%d", settings.api_host, settings.api_port)

    yield

    logger.info("OMKA 关闭中...")
    shutdown_scheduler()
    logger.info("OMKA 已关闭")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Oh My Knowledge Assistant - 个人智能知识助手",
    lifespan=lifespan,
    debug=settings.debug,
)


@app.get("/health", tags=["系统"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
    }


from omka.app.api import routes_digest, routes_feedback, routes_knowledge, routes_sources
app.include_router(routes_sources.router, prefix="/sources", tags=["信息源"])
app.include_router(routes_feedback.router, prefix="/candidates", tags=["候选池"])
app.include_router(routes_digest.router, prefix="/digests", tags=["每日简报"])
app.include_router(routes_knowledge.router, prefix="/knowledge", tags=["知识库"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "omka.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
    )

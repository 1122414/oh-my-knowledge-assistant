"""OMKA FastAPI 入口

提供 API 路由和生命周期管理。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.core.scheduler import schedule_daily_job, shutdown_scheduler, start_scheduler
from omka.app.storage.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("OMKA 启动中 | 版本=%s | 环境=%s", settings.app_version, settings.app_env)

    # 初始化数据库
    init_db()

    # 启动调度器
    start_scheduler()

    # TODO: 注册每日任务（Phase 5 完成后启用）
    # from omka.app.services.daily_job import run_daily_job
    # schedule_daily_job(run_daily_job)

    logger.info("OMKA 启动完成 | API=http://%s:%d", settings.api_host, settings.api_port)

    yield

    # 关闭
    logger.info("OMKA 关闭中...")
    shutdown_scheduler()
    logger.info("OMKA 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Oh My Knowledge Assistant - 个人智能知识助手",
    lifespan=lifespan,
    debug=settings.debug,
)


# 健康检查
@app.get("/health", tags=["系统"])
async def health_check():
    """服务健康检查"""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
    }


# TODO: Phase 1 完成后注册路由
# from omka.app.api import routes_sources, routes_digest, routes_feedback, routes_knowledge
# app.include_router(routes_sources.router, prefix="/sources", tags=["信息源"])
# app.include_router(routes_digest.router, prefix="/digests", tags=["每日简报"])
# app.include_router(routes_feedback.router, prefix="/candidates", tags=["候选池"])
# app.include_router(routes_knowledge.router, prefix="/knowledge", tags=["知识库"])

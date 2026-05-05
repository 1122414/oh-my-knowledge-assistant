from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from omka.app.core.config import settings
from omka.app.core.logging import TraceContext, get_logger, logger
from omka.app.core.scheduler import schedule_daily_job, shutdown_scheduler, start_scheduler
from omka.app.core.settings_service import init_default_settings
from omka.app.storage.db import init_db
from omka.app.storage.repositories import load_profile_sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OMKA 启动中 | 版本=%s | 环境=%s", settings.app_version, settings.app_env)

    init_db()

    try:
        init_default_settings()
    except Exception as e:
        logger.warning("初始化默认配置失败 | error=%s", e)

    loaded = load_profile_sources()
    if loaded > 0:
        logger.info("从配置文件加载 %d 个数据源", loaded)

    start_scheduler()

    from omka.app.services.daily_job import run_daily_job
    schedule_daily_job(run_daily_job)

    _start_feishu_ws()

    logger.info("OMKA 启动完成 | API=http://%s:%d", settings.api_host, settings.api_port)

    yield

    logger.info("OMKA 关闭中...")
    _stop_feishu_ws()
    shutdown_scheduler()
    logger.info("OMKA 已关闭")


def _start_feishu_ws():
    from omka.app.core.settings_service import get_setting
    from omka.app.integrations.feishu.config import FeishuConfig
    from omka.app.integrations.feishu.ws_client import init_ws_client

    if not get_setting("feishu_enabled", False):
        return

    config = FeishuConfig(
        enabled=True,
        app_id=get_setting("feishu_app_id", ""),
        app_secret=get_setting("feishu_app_secret", ""),
        verification_token=get_setting("feishu_verification_token", ""),
        encrypt_key=get_setting("feishu_encrypt_key", ""),
        command_prefix=get_setting("feishu_command_prefix", "/omka"),
        agent_conversation_enabled=get_setting("feishu_agent_conversation_enabled", False),
        auto_bind_direct_chat=get_setting("feishu_auto_bind_direct_chat", True),
    )

    if not config.is_configured():
        return

    ws_client = init_ws_client(config)
    ws_client.start()


def _stop_feishu_ws():
    from omka.app.integrations.feishu.ws_client import get_ws_client
    ws_client = get_ws_client()
    if ws_client:
        ws_client.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Oh My Knowledge Assistant - 个人智能知识助手",
    lifespan=lifespan,
    debug=settings.debug,
)

# CORS 配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 请求/响应日志中间件
from omka.app.api.middleware import APILoggingMiddleware
app.add_middleware(APILoggingMiddleware)


@app.get("/health", tags=["系统"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
    }


from omka.app.api import routes_agent, routes_asset, routes_digest, routes_feishu, routes_feedback, routes_jobs, routes_knowledge, routes_memory, routes_notifications, routes_push, routes_recommendation, routes_settings, routes_sources
app.include_router(routes_sources.router, prefix="/sources", tags=["信息源"])
app.include_router(routes_feedback.router, prefix="/candidates", tags=["候选池"])
app.include_router(routes_digest.router, prefix="/digests", tags=["每日简报"])
app.include_router(routes_knowledge.router, prefix="/knowledge", tags=["知识库"])
app.include_router(routes_memory.router, prefix="/memories", tags=["记忆"])
app.include_router(routes_recommendation.router, prefix="/recommendations", tags=["推荐"])
app.include_router(routes_push.router, prefix="/push", tags=["推送"])
app.include_router(routes_asset.router, prefix="/assets", tags=["资产"])
app.include_router(routes_settings.router, prefix="/settings", tags=["设置"])
app.include_router(routes_notifications.router, prefix="/notifications", tags=["通知"])
app.include_router(routes_jobs.router, prefix="/jobs", tags=["任务"])
app.include_router(routes_feishu.router, prefix="/integrations/feishu", tags=["飞书集成"])
app.include_router(routes_agent.router, prefix="/agent", tags=["Agent"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "omka.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
    )

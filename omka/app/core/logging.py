"""OMKA 全链路日志系统

设计目标：Agent 行为全链路可追溯监测

特性：
- 按日分文件夹（logs/YYYY-MM-DD/）
- 按域分文件（app/agent/pipeline/feishu/api/system/errors）
- 每条日志携带 (filename:lineno) + 函数名
- @trace 装饰器自动记录函数入口/出口/异常/耗时
- TraceContext 跨函数传递追踪 ID，串联调用链

用法：
    from omka.app.core.logging import get_logger, trace, TraceContext

    logger = get_logger("agent")  # → logs/YYYY-MM-DD/agent.log

    @trace
    async def my_func():
        ...
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

from omka.app.core.config import settings

# ============================================================
# TraceContext — 跨函数调用链串联
# ============================================================

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_trace_spans: ContextVar[list[dict[str, Any]]] = ContextVar("trace_spans")


class TraceContext:
    """分布式追踪上下文，串联一次请求/任务的所有日志。

    用法：
        with TraceContext("daily_job"):
            await fetch_all_sources()
            await run_ranking()
        # 该上下文内所有日志自动携带相同 trace_id
    """

    def __init__(self, name: str, metadata: dict[str, Any] | None = None):
        self.name = name
        self.metadata = metadata or {}
        self._token: Any = None
        self._spans_token: Any = None

    def __enter__(self):
        self._token = _trace_id.set(uuid.uuid4().hex[:12])
        self._spans_token = _trace_spans.set([])
        if _root_logger is not None:
            _root_logger.info(
                "[TRACE START] %s | trace_id=%s | meta=%s",
                self.name, _trace_id.get(), self.metadata,
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        spans = _trace_spans.get()
        total_ms = sum(s.get("elapsed_ms", 0) for s in spans)
        status = "FAILED" if exc_type else "OK"
        if _root_logger is not None:
            _root_logger.info(
            "[TRACE END] %s | status=%s | spans=%d | total_elapsed=%.1fms | trace_id=%s",
            self.name, status, len(spans), total_ms, _trace_id.get(),
        )
        _trace_id.reset(self._token)
        _trace_spans.reset(self._spans_token)
        return False

    @staticmethod
    def current_id() -> str:
        return _trace_id.get() or ""

    @staticmethod
    def add_span(name: str, elapsed_ms: float, **kwargs: Any):
        try:
            spans = _trace_spans.get()
        except LookupError:
            return
        span = {"name": name, "elapsed_ms": round(elapsed_ms, 2), **kwargs}
        spans.append(span)


# ============================================================
# 日志格式器 — 携带 (file:line) + 函数名
# ============================================================

class TraceFormatter(logging.Formatter):
    """自定义格式器：每条日志携带调用位置 (filename:lineno) + 函数名 + trace_id。

    控制台输出保持简洁（无文件路径），文件输出包含完整信息。
    """

    def __init__(self, fmt: str, datefmt: str, *, for_console: bool = False):
        super().__init__(fmt, datefmt)
        self.for_console = for_console

    def format(self, record: logging.LogRecord) -> str:
        # 注入调用位置（如果未被显式设置）
        if not getattr(record, "custom_location", False):
            fname = Path(record.pathname).name if hasattr(record, "pathname") else "?"
            record.filename_lineno = f"{fname}:{record.lineno}"
            record.func_name = record.funcName or "?"
        else:
            record.filename_lineno = getattr(record, "filename_lineno", "?:?")
            record.func_name = getattr(record, "func_name", "?")

        # 注入 trace_id
        tid = TraceContext.current_id()
        record.trace_id = f"[{tid}] " if tid else ""

        if self.for_console:
            # 控制台：省略路径，保持简洁
            return super().format(record)
        return super().format(record)


class ColoredConsoleFormatter(TraceFormatter):
    """带颜色的控制台格式器"""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname_colored = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


# ============================================================
# 日志工厂 — 按域创建独立 Logger + 文件 Handler
# ============================================================

# 日志域定义
_LOG_DOMAINS: dict[str, dict] = {
    "app":       {"filename": "app.log",       "description": "应用生命周期/启动/关闭"},
    "agent":     {"filename": "agent.log",     "description": "Agent 推理全链路"},
    "pipeline":  {"filename": "pipeline.log",  "description": "数据流水线各阶段"},
    "feishu":    {"filename": "feishu.log",    "description": "飞书消息/事件/命令"},
    "api":       {"filename": "api.log",       "description": "HTTP 请求/响应"},
    "daily_job": {"filename": "daily_job.log", "description": "每日任务编排"},
    "system":    {"filename": "system.log",    "description": "调度器/配置/基础设施"},
    "errors":    {"filename": "errors.log",    "description": "所有 ERROR+ 聚合"},
}

# 日志根目录
LOG_ROOT = Path(os.environ.get("OMKA_LOG_ROOT", settings.log_dir))

# 全局根 logger（兼容旧代码）
_root_logger: logging.Logger | None = None

# 已创建的域 logger 缓存
_domain_loggers: dict[str, logging.Logger] = {}

# 全局 log level 覆盖
_log_level_override: int | None = None


def _get_today_dir() -> Path:
    """获取当天的日志文件夹路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return LOG_ROOT / today


def _get_domain_log_path(domain: str) -> Path:
    """获取域日志文件的完整路径"""
    today_dir = _get_today_dir()
    today_dir.mkdir(parents=True, exist_ok=True)
    return today_dir / _LOG_DOMAINS[domain]["filename"]


def _create_file_handler(log_path: Path, level: int, *, for_errors: bool = False) -> RotatingFileHandler:
    """创建文件 handler"""
    handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_file_max_bytes,
        backupCount=settings.log_file_backup_count,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level if not for_errors else logging.WARNING)

    # 文件格式：完整时间 + 级别 + 位置 + trace_id + 消息
    file_fmt = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | "
        "%(filename_lineno)-24s | %(func_name)-20s | "
        "%(trace_id)s%(message)s"
    )
    file_formatter = TraceFormatter(file_fmt, datefmt="%Y-%m-%d %H:%M:%S", for_console=False)
    handler.setFormatter(file_formatter)
    return handler


def _create_console_handler(level: int) -> logging.StreamHandler:
    """创建控制台 handler（带颜色）"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    console_fmt = (
        "%(asctime)s | %(levelname_colored)-18s | "
        "%(filename_lineno)-20s | "
        "%(trace_id)s%(message)s"
    )
    console_formatter = ColoredConsoleFormatter(console_fmt, datefmt="%H:%M:%S", for_console=True)
    handler.setFormatter(console_formatter)
    return handler


def get_logger(domain: str = "app") -> logging.Logger:
    """获取指定域的日志记录器。

    Args:
        domain: 日志域名称，可选值：
            app, agent, pipeline, feishu, api, daily_job, system, errors

    Returns:
        配置好的 Logger 实例

    用法：
        logger = get_logger("agent")
        logger.info("开始构建上下文 | user_id=%s", uid)
    """
    global _root_logger, _domain_loggers

    if domain not in _LOG_DOMAINS:
        domain = "app"

    if domain in _domain_loggers:
        return _domain_loggers[domain]

    # 首次创建：初始化根 logger（仅一次）
    if _root_logger is None:
        _init_root_logger()

    # 确定日志级别
    log_level = _get_effective_level()

    # 创建域 logger
    logger = logging.getLogger(f"OMKA.{domain}")
    logger.setLevel(log_level)
    logger.propagate = False  # 不向根 logger 冒泡，避免重复输出

    # 域文件 handler
    log_path = _get_domain_log_path(domain)
    file_handler = _create_file_handler(log_path, log_level)
    logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = _create_console_handler(log_level)
    logger.addHandler(console_handler)

    # 错误聚合：ERROR+ 也写到 errors.log
    if domain != "errors":
        errors_path = _get_domain_log_path("errors")
        errors_handler = _create_file_handler(errors_path, log_level, for_errors=True)
        logger.addHandler(errors_handler)

    _domain_loggers[domain] = logger
    return logger


def _init_root_logger() -> None:
    """初始化根 logger（兼容旧代码 from omka.app.core.logging import logger）"""
    global _root_logger

    _root_logger = logging.getLogger("OMKA")
    _root_logger.setLevel(_get_effective_level())

    if _root_logger.handlers:
        return

    # 根 logger 的 app.log handler
    app_path = _get_domain_log_path("app")
    app_handler = _create_file_handler(app_path, _get_effective_level())
    _root_logger.addHandler(app_handler)

    # 控制台
    console_handler = _create_console_handler(_get_effective_level())
    _root_logger.addHandler(console_handler)

    # 错误聚合
    errors_path = _get_domain_log_path("errors")
    errors_handler = _create_file_handler(errors_path, _get_effective_level(), for_errors=True)
    _root_logger.addHandler(errors_handler)

    # 降低第三方库日志噪音
    for lib in ["apscheduler", "httpx", "sqlalchemy.engine", "httpcore", "urllib3", "lark"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    _root_logger.info(
        "日志系统初始化完成 | root=%s | level=%s | today=%s",
        LOG_ROOT, logging.getLevelName(_get_effective_level()), _get_today_dir().name,
    )


def _get_effective_level() -> int:
    """获取有效日志级别"""
    if _log_level_override is not None:
        return _log_level_override
    level_name = settings.log_level.upper()
    return getattr(logging, level_name, logging.INFO)


def set_log_level(level: str | int) -> None:
    """运行时修改日志级别

    Args:
        level: 日志级别名（"DEBUG"/"INFO"/...）或数值
    """
    global _log_level_override
    if isinstance(level, str):
        _log_level_override = getattr(logging, level.upper(), logging.INFO)
    else:
        _log_level_override = level

    if _log_level_override is not None:
        # 更新所有已创建的 logger
        for lg in _domain_loggers.values():
            lg.setLevel(_log_level_override)
        if _root_logger is not None:
            _root_logger.setLevel(_log_level_override)


# ============================================================
# @trace 装饰器 — 自动记录函数入口/出口/异常/耗时
# ============================================================

F = TypeVar("F", bound=Callable[..., Any])


def _format_args(args: tuple, kwargs: dict, max_len: int = 200) -> str:
    """安全格式化函数参数（截断长字符串，隐藏敏感信息）"""
    parts = []

    # 跳过 self/cls
    start = 1 if args and (getattr(args[0], "__class__", None) or inspect.isclass(type(args[0]))) else 0
    for a in args[start:]:
        s = str(a)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(s)

    for k, v in kwargs.items():
        s = str(v)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(f"{k}={s}")

    return ", ".join(parts)[:max_len * 2]


def trace(
    domain: str = "app",
    log_args: bool = False,
    log_result: bool = False,
    max_result_len: int = 200,
):
    def decorator(func: F) -> F:
        logger_name = domain
        is_async = inspect.iscoroutinefunction(func)

        # 如果日志追踪被禁用，直接返回原函数
        if not settings.log_trace_enabled:
            return func

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(logger_name)
            qualname = _caller_info(func)

            # 入口日志
            entry_msg = f"[→] {qualname} 开始"
            if log_args:
                args_str = _format_args(args, kwargs)
                if args_str:
                    entry_msg += f" | args=({args_str})"
            logger.debug(entry_msg)

            t0 = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000

                # 出口日志
                exit_msg = f"[←] {qualname} 完成 | elapsed={elapsed:.1f}ms"
                if log_result and result is not None:
                    res_str = str(result)
                    if len(res_str) > max_result_len:
                        res_str = res_str[:max_result_len] + "..."
                    exit_msg += f" | result={res_str}"
                logger.debug(exit_msg)

                # 注册到 TraceContext
                TraceContext.add_span(qualname, elapsed)

                return result
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                logger.error(
                    "[✗] %s 异常 | elapsed=%.1fms | error=%s: %s",
                    qualname, elapsed, type(e).__name__, e,
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(logger_name)
            qualname = _caller_info(func)

            entry_msg = f"[→] {qualname} 开始"
            if log_args:
                args_str = _format_args(args, kwargs)
                if args_str:
                    entry_msg += f" | args=({args_str})"
            logger.debug(entry_msg)

            t0 = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000

                exit_msg = f"[←] {qualname} 完成 | elapsed={elapsed:.1f}ms"
                if log_result and result is not None:
                    res_str = str(result)
                    if len(res_str) > max_result_len:
                        res_str = res_str[:max_result_len] + "..."
                    exit_msg += f" | result={res_str}"
                logger.debug(exit_msg)

                TraceContext.add_span(qualname, elapsed)

                return result
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                logger.error(
                    "[✗] %s 异常 | elapsed=%.1fms | error=%s: %s",
                    qualname, elapsed, type(e).__name__, e,
                )
                raise

        return cast(F, async_wrapper if is_async else sync_wrapper)

    return decorator


def _caller_info(func: Callable) -> str:
    """获取调用者信息字符串，格式: module.ClassName.method_name"""
    module = func.__module__.split(".")[-1] if func.__module__ else "?"
    qual = func.__qualname__ if hasattr(func, "__qualname__") else func.__name__
    return f"{module}.{qual}"


# ============================================================
# 工具函数：用调用位置信息创建日志记录
# ============================================================

def _make_record(
    logger: logging.Logger,
    level: int,
    msg: str,
    filename: str,
    lineno: int,
    func_name: str,
    *args: Any,
) -> None:
    """创建携带精确调用位置的日志记录"""
    record = logger.makeRecord(
        logger.name, level, filename, lineno, msg, args, None, func_name,
    )
    setattr(record, "custom_location", True)
    setattr(record, "filename_lineno", f"{filename}:{lineno}")
    setattr(record, "func_name", func_name)
    logger.handle(record)


# ============================================================
# 兼容旧代码：保留模块级 logger 变量
# ============================================================

# 初始化根 logger 并赋值给模块级 `logger` 变量
# 这样 `from omka.app.core.logging import logger` 仍然可用
logger = get_logger("app")

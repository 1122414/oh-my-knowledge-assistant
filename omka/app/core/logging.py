"""OMKA 日志配置

统一日志格式，支持控制台输出和文件轮转。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from omka.app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式器"""

    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str | None = None,
    log_dir: Path | None = None,
    app_name: str = "OMKA",
) -> logging.Logger:
    """配置应用日志

    Args:
        level: 日志级别，默认从配置读取
        log_dir: 日志目录，默认从配置读取
        app_name: 应用名称

    Returns:
        配置好的根日志记录器
    """
    log_level = (level or settings.log_level).upper()
    log_directory = log_dir or settings.log_dir

    # 确保日志目录存在
    log_directory.mkdir(parents=True, exist_ok=True)

    # 根日志记录器
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 统一格式
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # 控制台 handler（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = ColoredFormatter(fmt, datefmt=datefmt)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件 handler（轮转）
    log_file = log_directory / f"{app_name.lower()}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.log_file_max_bytes,
        backupCount=settings.log_file_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(fmt, datefmt=datefmt)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 降低第三方库的日志级别
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger.info("日志系统初始化完成 | 级别=%s | 文件=%s", log_level, log_file)
    return logger


# 全局日志记录器
logger = setup_logging()

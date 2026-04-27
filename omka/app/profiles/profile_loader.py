from pathlib import Path
from typing import Any

import yaml

from omka.app.core.config import settings
from omka.app.core.logging import logger


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.warning("配置文件不存在 | path=%s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_interests() -> list[dict[str, Any]]:
    data = load_yaml(settings.profiles_dir / "interests.yaml")
    return data.get("interests", [])


def load_projects() -> list[dict[str, Any]]:
    data = load_yaml(settings.profiles_dir / "projects.yaml")
    return data.get("projects", [])


def load_sources_config() -> dict[str, Any]:
    return load_yaml(settings.profiles_dir / "sources.yaml")




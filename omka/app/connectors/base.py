from abc import ABC, abstractmethod
from typing import Any


class SourceConnector(ABC):
    """信息源连接器抽象基类

    所有信息源（GitHub、RSS、Web 等）必须实现此接口。
    """

    source_type: str = ""

    @abstractmethod
    async def fetch(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """从信息源抓取原始数据

        Args:
            config: 数据源配置

        Returns:
            原始数据列表
        """
        ...

    @abstractmethod
    def normalize(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """将原始数据转换为统一结构

        Args:
            raw_item: 原始数据项

        Returns:
            NormalizedItem 字典
        """
        ...

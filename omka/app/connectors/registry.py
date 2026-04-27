from omka.app.connectors.base import SourceConnector
from omka.app.connectors.github.connector import GitHubConnector
from omka.app.core.logging import logger


class ConnectorRegistry:
    _connectors: dict[str, type[SourceConnector]] = {
        "github": GitHubConnector,
    }

    @classmethod
    def register(cls, source_type: str, connector_cls: type[SourceConnector]) -> None:
        cls._connectors[source_type] = connector_cls
        logger.info("注册 Connector | type=%s | class=%s", source_type, connector_cls.__name__)

    @classmethod
    def get(cls, source_type: str) -> SourceConnector:
        connector_cls = cls._connectors.get(source_type)
        if not connector_cls:
            raise ValueError(f"未注册的 Connector 类型: {source_type}")
        return connector_cls()

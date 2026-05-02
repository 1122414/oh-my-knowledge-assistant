from typing import Any

from omka.app.core.logging import logger
from omka.app.pipeline.ranker import rank_candidates as _rank_candidates


def run_ranking() -> dict[str, Any]:
    logger.info("通过 RecommendationService 执行排序")
    return _rank_candidates()

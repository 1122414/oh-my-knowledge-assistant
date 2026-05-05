from datetime import datetime
from pathlib import Path
from typing import Any

from omka.app.core.config import settings
from omka.app.core.logging import get_logger, trace
from omka.app.storage.db import CandidateItem, NormalizedItem, get_session
from sqlmodel import select

logger = get_logger("pipeline")


@trace("pipeline")
async def generate_digest() -> dict[str, Any]:
    from omka.app.pipeline.summarizer import LLMClient
    llm = LLMClient()

    with get_session() as session:
        candidates = session.exec(
            select(CandidateItem)
            .where(CandidateItem.status == "pending")
            .order_by(CandidateItem.score.desc())
            .limit(settings.digest_top_n)
        ).all()

    if not candidates:
        logger.info("没有候选条目可生成简报")
        return {"digest_path": None, "item_count": 0}

    digest_items = []
    for candidate in candidates:
        try:
            if not candidate.summary:
                normalized = None
                with get_session() as session:
                    normalized = session.get(NormalizedItem, candidate.normalized_item_id)
                if normalized:
                    result = await llm.summarize(
                        candidate.title,
                        normalized.content,
                        candidate.item_type,
                    )
                    candidate.summary = result["summary"]
                    candidate.recommendation_reason = result["recommendation_reason"]
                    with get_session() as session:
                        session.merge(candidate)
                        session.commit()

            digest_items.append({
                "title": candidate.title,
                "url": candidate.url,
                "type": candidate.item_type,
                "score": candidate.score,
                "summary": candidate.summary or "",
                "recommendation_reason": candidate.recommendation_reason or "",
                "matched_interests": candidate.matched_interests,
                "matched_projects": candidate.matched_projects,
                "score_detail": candidate.score_detail,
            })
        except Exception as e:
            logger.error("生成摘要失败 | candidate=%s | error=%s", candidate.id, e)
            continue

    date_str = datetime.now().strftime("%Y-%m-%d")
    digest_path = build_markdown_digest(date_str, digest_items)

    with get_session() as session:
        for candidate in candidates:
            candidate.status = "digested"
            session.add(candidate)
        session.commit()

    logger.info("简报生成完成 | path=%s | items=%d", digest_path, len(digest_items))
    return {"digest_path": str(digest_path), "item_count": len(digest_items)}


def build_markdown_digest(date_str: str, items: list[dict[str, Any]]) -> Path:
    settings.digests_dir.mkdir(parents=True, exist_ok=True)
    filepath = settings.digests_dir / f"{date_str}.md"

    lines = [
        f"# 今日 GitHub 知识简报 | {date_str}",
        "",
        f"> 共 {len(items)} 条推荐内容",
        "",
        "---",
        "",
    ]

    for i, item in enumerate(items, 1):
        score = item.get("score", 0)
        detail = item.get("score_detail", {})

        lines.append(f"## {i}. {item['title']}")
        lines.append("")

        summary = item.get("summary", "")
        if summary:
            lines.append(summary)
            lines.append("")

        lines.extend(_build_score_explanation(score, detail))

        lines.append(f"- **链接**: {item['url']}")
        lines.append(f"- **类型**: {item['type']}")
        reason = item.get("recommendation_reason", "")
        if reason:
            lines.append(f"- **推荐理由**: {reason}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 候选入库",
        "",
    ])
    for item in items:
        lines.append(f"- [ ] [{item['title']}]({item['url']})")
    lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def _build_score_explanation(final_score: float, detail: dict) -> list[str]:
    """构建评分解释，展示各维度得分和原因"""
    from omka.app.core.config import settings

    lines = [f"**评分**: {final_score:.2f}", ""]

    interest = detail.get("interest_score", 0)
    project = detail.get("project_score", 0)
    freshness = detail.get("freshness_score", 0)
    popularity = detail.get("popularity_score", 0)
    source_quality = detail.get("source_quality_score", 0)

    matched_interests = detail.get("matched_interests", [])
    matched_projects = detail.get("matched_projects", [])

    items = []
    items.append(
        f"兴趣匹配 {interest:.2f} "
        f"(权重 {settings.score_weight_interest:.0%})"
        + (f": {', '.join(matched_interests)}" if matched_interests else "")
    )
    items.append(
        f"项目相关 {project:.2f} "
        f"(权重 {settings.score_weight_project:.0%})"
        + (f": {', '.join(matched_projects)}" if matched_projects else "")
    )
    items.append(f"新鲜度 {freshness:.2f} (权重 {settings.score_weight_freshness:.0%})")
    items.append(f"热度 {popularity:.2f} (权重 {settings.score_weight_popularity:.0%})")
    items.append(f"源头质量 {source_quality:.2f} (权重 {settings.score_weight_source_quality:.0%})")

    lines.append("> 评分详情:")
    for item_line in items:
        lines.append(f"> - {item_line}")
    lines.append("")

    return lines

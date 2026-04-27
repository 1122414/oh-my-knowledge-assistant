from datetime import datetime
from pathlib import Path
from typing import Any

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.pipeline.summarizer import LLMClient
from omka.app.storage.db import CandidateItem, NormalizedItem, get_session
from sqlmodel import select


async def generate_digest() -> dict[str, Any]:
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
            })
        except Exception as e:
            logger.error("生成摘要失败 | candidate=%s | error=%s", candidate.id, e)
            continue

    date_str = datetime.now().strftime("%Y-%m-%d")
    digest_path = build_markdown_digest(date_str, digest_items)

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
        lines.extend([
            f"## {i}. {item['title']}",
            "",
            f"- **链接**: {item['url']}",
            f"- **类型**: {item['type']}",
            f"- **得分**: {item['score']}",
            f"- **摘要**: {item['summary']}",
            f"- **推荐理由**: {item['recommendation_reason']}",
        ])
        if item.get("matched_interests"):
            lines.append(f"- **相关兴趣**: {', '.join(item['matched_interests'])}")
        if item.get("matched_projects"):
            lines.append(f"- **相关项目**: {', '.join(item['matched_projects'])}")
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

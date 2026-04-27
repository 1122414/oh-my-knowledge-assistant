from datetime import datetime
from pathlib import Path
from typing import Any

from omka.app.core.config import settings


def save_knowledge_markdown(item: dict[str, Any]) -> Path:
    repo = item.get("repo_full_name", "unknown")
    safe_name = repo.replace("/", "_")
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{safe_name}_{date_str}.md"

    dir_path = settings.knowledge_dir / "github"
    dir_path.mkdir(parents=True, exist_ok=True)
    filepath = dir_path / filename

    lines = [
        f"# {item['title']}",
        "",
        f"- **链接**: {item['url']}",
        f"- **类型**: {item['item_type']}",
        f"- **作者**: {item.get('author', 'N/A')}",
        f"- **入库时间**: {datetime.now().isoformat()}",
        "",
        "## 摘要",
        "",
        item.get("summary", ""),
        "",
        "## 内容",
        "",
        item.get("content", ""),
        "",
    ]

    if item.get("tags"):
        lines.extend([
            "## 标签",
            "",
            ", ".join(item["tags"]),
            "",
        ])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath

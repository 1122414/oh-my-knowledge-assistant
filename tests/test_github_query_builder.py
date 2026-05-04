"""GitHub Search query builder 测试"""

from omka.app.connectors.github.search_task import SearchTask
from omka.app.connectors.github.query_builder import (
    build_github_queries,
    build_base_query,
    build_negative_part,
    build_metadata,
)


def test_basic_query():
    task = SearchTask(name="Test", query="agent framework")
    queries = build_github_queries(task)
    assert len(queries) >= 1
    assert len(queries) <= 6
    q = queries[0]
    assert "agent framework" in q["query"]
    assert "archived:false" in q["query"]
    assert "fork:false" in q["query"]


def test_star_band_query():
    task = SearchTask(name="Test", query="agent", star_bands=["20..300", "300..5000"])
    queries = build_github_queries(task)
    star_bands_seen = set(q["star_band"] for q in queries)
    assert "20..300" in star_bands_seen or "300..5000" in star_bands_seen


def test_language_query():
    task = SearchTask(name="Test", query="agent", languages=["Python"])
    queries = build_github_queries(task)
    has_lang = any("language:Python" in q["query"] for q in queries)
    assert has_lang


def test_negative_terms():
    task = SearchTask(
        name="Test", query="agent",
        negative_terms=["awesome", "tutorial"]
    )
    neg = build_negative_part(task)
    assert "NOT awesome" in neg
    assert "NOT tutorial" in neg


def test_metadata():
    task = SearchTask(name="My Task", query="test", intent="discover_tool", priority=1.5)
    queries = build_github_queries(task)
    meta = build_metadata(task, queries[0])
    assert meta["search_task_name"] == "My Task"
    assert meta["search_task_intent"] == "discover_tool"
    assert meta["search_task_priority"] == 1.5
    assert meta["search_strategy"] in ("best_match", "updated", "stars")


def test_noise_only_in_negative():
    """非噪声 negative terms 不加 NOT"""
    task = SearchTask(name="T", query="q", negative_terms=["demo", "sandbox"])
    neg = build_negative_part(task)
    assert "NOT demo" in neg
    assert "NOT sandbox" not in neg


def test_request_limit():
    task = SearchTask(name="T", query="q", languages=["Python", "TypeScript", "Go"])
    queries = build_github_queries(task)
    assert len(queries) <= task.max_requests


if __name__ == "__main__":
    test_basic_query()
    test_star_band_query()
    test_language_query()
    test_negative_terms()
    test_metadata()
    test_noise_only_in_negative()
    test_request_limit()
    print("All query builder tests passed!")

"""搜索质量评分测试

覆盖:
- 源头过滤规则 (archived/fork/stale/must_terms/low_source_quality)
- 过滤原因统计
- 搜索报告生成
"""

from omka.app.connectors.github.connector import _check_source_filter
from omka.app.connectors.github.search_task import SearchTask
from omka.app.services.push_quality_report import SearchQualityReport, SearchTaskReport


def test_filter_archived():
    task = SearchTask(name="T", query="q")
    item = {"archived": True, "full_name": "test/repo"}
    assert _check_source_filter(item, task) == "archived_or_disabled"


def test_filter_fork():
    task = SearchTask(name="T", query="q")
    item = {"fork": True, "full_name": "test/repo", "stargazers_count": 100}
    assert _check_source_filter(item, task) == "fork"


def test_filter_low_stars():
    task = SearchTask(name="T", query="q", star_bands=["50..500"])
    item = {"stargazers_count": 10, "full_name": "test/repo"}
    assert _check_source_filter(item, task) == "low_stars"


def test_filter_must_terms_not_matched():
    task = SearchTask(name="T", query="q", must_terms=["agent", "llm"])
    item = {
        "full_name": "test/repo", "name": "test", "description": "simple util",
        "topics": [], "stargazers_count": 100,
    }
    assert _check_source_filter(item, task) == "must_terms_not_matched"


def test_filter_pass():
    task = SearchTask(name="T", query="q", must_terms=["agent"], star_bands=["20..300"])
    item = {
        "full_name": "test/repo", "name": "agent-tool", "description": "agent framework",
        "topics": ["ai"], "stargazers_count": 100, "pushed_at": "2026-05-01T00:00:00Z",
    }
    assert _check_source_filter(item, task) is None


def test_quality_report():
    report = SearchQualityReport()
    task_report = SearchTaskReport(
        name="Test Task", intent="discover_tool",
        request_count=4, fetched_count=18, unique_count=9,
        filtered_count=5, candidate_count=4,
        filter_reasons={"archived": 1, "stale": 2, "low_stars": 2},
        top_repos=["owner/repo1", "owner/repo2"],
    )
    report.search_tasks.append(task_report)
    report.total_request_count = 4
    report.total_unique_repos = 9
    report.total_candidates = 4

    d = report.to_dict()
    assert len(d["search_tasks"]) == 1
    assert d["search_tasks"][0]["candidate_count"] == 4
    assert d["total_candidates"] == 4


if __name__ == "__main__":
    test_filter_archived()
    test_filter_fork()
    test_filter_low_stars()
    test_filter_must_terms_not_matched()
    test_filter_pass()
    test_quality_report()
    print("All quality scoring tests passed!")

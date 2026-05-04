"""SearchTask 模型 + 向后兼容测试"""

from omka.app.connectors.github.search_task import (
    SearchTask,
    search_task_from_config,
    search_tasks_from_yaml,
)

def test_old_config_compatibility():
    """旧配置 name/query/limit 可转换"""
    task = search_task_from_config({"name": "Test", "query": "test query", "limit": 3})
    assert task.name == "Test"
    assert task.query == "test query"
    assert task.limit == 3
    assert task.enabled is True
    assert task.intent == "discover_tool"
    assert task.star_bands == ["20..300", "300..5000"]
    assert task.pushed_after_days == 365


def test_new_config_full():
    """新配置所有字段可加载"""
    task = search_task_from_config({
        "name": "Agent Test",
        "query": "agent framework",
        "enabled": True,
        "intent": "discover_framework",
        "description": "Find agent frameworks",
        "priority": 1.2,
        "must_terms": ["agent", "llm"],
        "nice_terms": ["playwright"],
        "negative_terms": ["awesome", "tutorial"],
        "languages": ["Python", "TypeScript"],
        "star_bands": ["20..300", "300..5000"],
        "pushed_after_days": 180,
        "limit_per_query": 5,
    })
    assert task.intent == "discover_framework"
    assert "agent" in task.must_terms
    assert "awesome" in task.negative_terms
    assert "Python" in task.languages
    assert task.pushed_after_days == 180
    assert task.priority == 1.2


def test_default_values():
    """缺省字段有合理默认值"""
    task = search_task_from_config({})
    assert task.name == "unnamed"
    assert task.query == ""
    assert task.enabled is True
    assert task.star_bands == ["20..300", "300..5000"]


def test_min_stars():
    """min_stars 从 star_bands 第一段提取"""
    task = SearchTask(name="T", query="q", star_bands=["50..500", "500..5000"])
    assert task.min_stars == 50


def test_max_requests():
    """max_requests 根据配置计算上限"""
    task = SearchTask(name="T", query="q")
    assert task.max_requests == 6


def test_yaml_loading():
    """从 YAML 数据加载搜索任务列表"""
    yaml_data = {
        "github": {
            "searches": [
                {"name": "S1", "query": "q1", "enabled": True},
                {"name": "S2", "query": "q2", "enabled": False},
            ]
        }
    }
    tasks = search_tasks_from_yaml(yaml_data)
    assert len(tasks) == 1
    assert tasks[0].name == "S1"


def test_invalid_intent():
    """无效 intent 抛异常"""
    try:
        SearchTask(name="T", query="q", intent="invalid")
        assert False, "Should raise ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_old_config_compatibility()
    test_new_config_full()
    test_default_values()
    test_min_stars()
    test_max_requests()
    test_yaml_loading()
    test_invalid_intent()
    print("All SearchTask tests passed!")

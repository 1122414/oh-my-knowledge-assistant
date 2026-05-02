#!/usr/bin/env python3
"""
OMKA 升级功能测试脚本

测试范围：Phase 0-5 新增功能
运行方式：python tests/test_upgrade_features.py
前提条件：后端服务已启动 (python -m omka.app.main)
"""

import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
client = httpx.Client(base_url=BASE_URL, timeout=30)


def check_health():
    """检查服务健康状态"""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    print(f"✅ 服务健康 | {data['app']} v{data['version']}")
    return True


def test_memory_apis():
    """测试记忆 API"""
    print("\n🧠 测试记忆 API...")

    # 创建记忆
    resp = client.post("/memories", json={
        "memory_type": "user",
        "subject": "test_subject",
        "content": "我最近重点关注多模态知识资产",
        "scope": "user",
        "importance": 0.8,
    })
    assert resp.status_code == 200
    memory_id = resp.json()["id"]
    print(f"  ✅ 创建记忆 | {memory_id}")

    # 查询记忆
    resp = client.get(f"/memories/{memory_id}")
    assert resp.status_code == 200
    print(f"  ✅ 查询记忆 | {resp.json()['content'][:30]}...")

    # 列表查询
    resp = client.get("/memories?memory_type=user&limit=5")
    assert resp.status_code == 200
    print(f"  ✅ 列表查询 | {resp.json()['total']} 条")

    # 确认记忆
    resp = client.post(f"/memories/{memory_id}/confirm")
    assert resp.status_code == 200
    print(f"  ✅ 确认记忆 | status={resp.json()['status']}")

    # 删除记忆
    resp = client.delete(f"/memories/{memory_id}")
    assert resp.status_code == 200
    print(f"  ✅ 删除记忆")

    # 记忆统计
    resp = client.get("/memories/profile/summary")
    assert resp.status_code == 200
    print(f"  ✅ 记忆统计 | user={resp.json()['user_memories']}")

    return True


def test_recommendation_apis():
    """测试推荐 API"""
    print("\n💡 测试推荐 API...")

    # 运行推荐
    resp = client.post("/recommendations/run", json={
        "trigger_type": "manual",
        "strategy": "default",
    })
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    print(f"  ✅ 运行推荐 | run_id={run_id}")

    # 最新推荐
    resp = client.get("/recommendations/latest")
    assert resp.status_code == 200
    print(f"  ✅ 最新推荐 | {resp.json().get('message', '有数据')}")

    # 推荐影响
    resp = client.get("/recommendations/profile-impact")
    assert resp.status_code == 200
    print(f"  ✅ 推荐影响 | runs={resp.json()['total_runs']}")

    return True


def test_push_apis():
    """测试推送 API"""
    print("\n📢 测试推送 API...")

    # 创建策略
    resp = client.post("/push/policies", json={
        "id": "test_daily",
        "name": "测试每日推送",
        "trigger_type": "daily",
        "max_per_day": 3,
    })
    assert resp.status_code == 200
    print(f"  ✅ 创建策略 | test_daily")

    # 列表策略
    resp = client.get("/push/policies")
    assert resp.status_code == 200
    print(f"  ✅ 列表策略 | {len(resp.json()['policies'])} 条")

    # 推送状态
    resp = client.get("/push/status")
    assert resp.status_code == 200
    print(f"  ✅ 推送状态 | today={resp.json()['today_pushes']}")

    # 更新策略
    resp = client.put("/push/policies/test_daily", json={
        "enabled": False,
    })
    assert resp.status_code == 200
    print(f"  ✅ 更新策略 | enabled=False")

    return True


def test_asset_apis():
    """测试资产 API"""
    print("\n📎 测试资产 API...")

    # 列表资产
    resp = client.get("/assets")
    assert resp.status_code == 200
    print(f"  ✅ 列表资产 | {len(resp.json()['assets'])} 条")

    return True


def test_feishu_commands():
    """测试飞书命令路由（通过模拟事件）"""
    print("\n💬 测试飞书命令解析...")

    from omka.app.integrations.feishu.command_router import FeishuCommandRouter
    from omka.app.integrations.feishu.config import FeishuConfig
    from omka.app.integrations.feishu.models import FeishuMessageEvent

    config = FeishuConfig(enabled=False, app_id="", app_secret="")
    router = FeishuCommandRouter(config)

    # 解析 help 命令
    cmd, args = router._parse_command('{"text": "/omka help"}')
    assert cmd == "help"
    print(f"  ✅ 解析 help 命令")

    # 解析 memory 命令
    cmd, args = router._parse_command('{"text": "/omka memory list"}')
    assert cmd == "memory"
    assert args == ["list"]
    print(f"  ✅ 解析 memory list 命令")

    # 解析 why 命令
    cmd, args = router._parse_command('{"text": "/omka why candidate:xxx"}')
    assert cmd == "why"
    assert args == ["candidate:xxx"]
    print(f"  ✅ 解析 why 命令")

    return True


def test_services():
    """测试服务层"""
    print("\n🔧 测试服务层...")

    from omka.app.services.memory_service import MemoryService
    from omka.app.services.recommendation_service import RecommendationService
    from omka.app.services.action_service import PushService, AssetService

    # MemoryService
    count = MemoryService.count_memories()
    print(f"  ✅ MemoryService | 记忆总数: {count}")

    # RecommendationService
    exp = RecommendationService.get_explanation("non_existent")
    assert exp is None
    print(f"  ✅ RecommendationService | 解释查询正常")

    # PushService
    today = PushService.count_today_events()
    print(f"  ✅ PushService | 今日推送: {today}")

    # AssetService
    assets = AssetService.list_assets()
    print(f"  ✅ AssetService | 资产总数: {len(assets)}")

    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("OMKA 升级功能测试")
    print("=" * 50)

    tests = [
        ("健康检查", check_health),
        ("记忆 API", test_memory_apis),
        ("推荐 API", test_recommendation_apis),
        ("推送 API", test_push_apis),
        ("资产 API", test_asset_apis),
        ("飞书命令", test_feishu_commands),
        ("服务层", test_services),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {name} 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

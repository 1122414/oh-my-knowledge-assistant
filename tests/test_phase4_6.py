"""Phase 4-6 功能测试脚本

测试内容：
- Push 策略管理 API
- 资产上传和管理 API
- 记忆管理 API
- 前端页面可访问性

运行前请确保：
1. 后端服务已启动: python -m omka.app.main
2. 前端已构建: cd frontend && npm run build

用法：
    python tests/test_phase4_6.py
"""

import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"


class TestRunner:
    def __init__(self):
        self.client = httpx.Client(base_url=BASE_URL, timeout=10)
        self.passed = 0
        self.failed = 0
        self.errors = []

    def test(self, name: str, func):
        try:
            func()
            print(f"  ✓ {name}")
            self.passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            self.failed += 1
            self.errors.append((name, str(e)))

    def report(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 50}")
        print(f"总计: {total} | 通过: {self.passed} | 失败: {self.failed}")
        if self.errors:
            print("\n失败项:")
            for name, err in self.errors:
                print(f"  - {name}: {err}")
        print("=" * 50)
        return self.failed == 0


# ===========================================
# Push Policy 测试
# ===========================================


def test_push_policy_list():
    r = httpx.get(f"{BASE_URL}/push/policies?enabled_only=false")
    assert r.status_code == 200
    data = r.json()
    assert "policies" in data


def test_push_policy_create():
    policy_id = f"test_policy_{int(time.time())}"
    r = httpx.post(
        f"{BASE_URL}/push/policies",
        json={
            "id": policy_id,
            "name": "测试策略",
            "trigger_type": "high_score",
            "threshold": 0.85,
            "max_per_day": 3,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == policy_id
    return policy_id


def test_push_policy_update(policy_id: str):
    r = httpx.put(
        f"{BASE_URL}/push/policies/{policy_id}",
        json={"enabled": False, "threshold": 0.9},
    )
    assert r.status_code == 200


def test_push_events():
    r = httpx.get(f"{BASE_URL}/push/events?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data


def test_push_status():
    r = httpx.get(f"{BASE_URL}/push/status")
    assert r.status_code == 200
    data = r.json()
    assert "today_pushes" in data


# ===========================================
# Asset 测试
# ===========================================


def test_asset_list():
    r = httpx.get(f"{BASE_URL}/assets")
    assert r.status_code == 200
    data = r.json()
    assert "assets" in data


def test_asset_upload():
    test_file = Path("tests/test_asset.txt")
    test_file.write_text("This is a test asset for OMKA.")
    try:
        with open(test_file, "rb") as f:
            r = httpx.post(
                f"{BASE_URL}/assets/upload",
                files={"file": ("test_asset.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["status"] == "uploaded"
        return data["id"]
    finally:
        test_file.unlink(missing_ok=True)


def test_asset_get(asset_id: str):
    r = httpx.get(f"{BASE_URL}/assets/{asset_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == asset_id


def test_asset_delete(asset_id: str):
    r = httpx.delete(f"{BASE_URL}/assets/{asset_id}")
    assert r.status_code == 200


# ===========================================
# Memory 测试
# ===========================================


def test_memory_list():
    r = httpx.get(f"{BASE_URL}/memories?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


def test_memory_create():
    r = httpx.post(
        f"{BASE_URL}/memories",
        json={
            "memory_type": "system",
            "subject": "测试记忆",
            "content": "这是一条用于测试的记忆内容",
            "scope": "global",
            "importance": 0.7,
            "tags": ["test", "phase6"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    return data["id"]


def test_memory_get(memory_id: str):
    r = httpx.get(f"{BASE_URL}/memories/{memory_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == memory_id


def test_memory_confirm(memory_id: str):
    r = httpx.post(f"{BASE_URL}/memories/{memory_id}/confirm")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"


def test_memory_delete(memory_id: str):
    r = httpx.delete(f"{BASE_URL}/memories/{memory_id}")
    assert r.status_code == 200


def test_memory_profile_summary():
    r = httpx.get(f"{BASE_URL}/memories/profile/summary")
    assert r.status_code == 200
    data = r.json()
    assert "user_memories" in data
    assert "conversation_memories" in data
    assert "system_memories" in data


# ===========================================
# 前端页面测试
# ===========================================


def test_frontend_push_page():
    r = httpx.get(f"{FRONTEND_URL}/push", follow_redirects=True)
    assert r.status_code == 200


def test_frontend_assets_page():
    r = httpx.get(f"{FRONTEND_URL}/assets", follow_redirects=True)
    assert r.status_code == 200


def test_frontend_memory_page():
    r = httpx.get(f"{FRONTEND_URL}/memory", follow_redirects=True)
    assert r.status_code == 200


# ===========================================
# 主程序
# ===========================================


def main():
    print("OMKA Phase 4-6 功能测试")
    print("=" * 50)

    runner = TestRunner()

    # 测试 Push Policy
    print("\n[Push Policy API]")
    runner.test("获取策略列表", test_push_policy_list)

    policy_id = None
    try:
        policy_id = test_push_policy_create()
        runner.passed += 1
        print("  ✓ 创建推送策略")
    except Exception as e:
        runner.failed += 1
        runner.errors.append(("创建推送策略", str(e)))
        print(f"  ✗ 创建推送策略: {e}")

    if policy_id:
        runner.test("更新推送策略", lambda: test_push_policy_update(policy_id))

    runner.test("获取推送事件", test_push_events)
    runner.test("获取推送状态", test_push_status)

    # 测试 Asset
    print("\n[Asset API]")
    runner.test("获取资产列表", test_asset_list)

    asset_id = None
    try:
        asset_id = test_asset_upload()
        runner.passed += 1
        print("  ✓ 上传资产")
    except Exception as e:
        runner.failed += 1
        runner.errors.append(("上传资产", str(e)))
        print(f"  ✗ 上传资产: {e}")

    if asset_id:
        runner.test("获取资产详情", lambda: test_asset_get(asset_id))
        runner.test("归档资产", lambda: test_asset_delete(asset_id))

    # 测试 Memory
    print("\n[Memory API]")
    runner.test("获取记忆列表", test_memory_list)

    memory_id = None
    try:
        memory_id = test_memory_create()
        runner.passed += 1
        print("  ✓ 创建记忆")
    except Exception as e:
        runner.failed += 1
        runner.errors.append(("创建记忆", str(e)))
        print(f"  ✗ 创建记忆: {e}")

    if memory_id:
        runner.test("获取记忆详情", lambda: test_memory_get(memory_id))
        runner.test("确认记忆", lambda: test_memory_confirm(memory_id))
        runner.test("删除记忆", lambda: test_memory_delete(memory_id))

    runner.test("获取记忆画像统计", test_memory_profile_summary)

    # 测试前端页面
    print("\n[Frontend Pages]")
    runner.test("Push 页面可访问", test_frontend_push_page)
    runner.test("Assets 页面可访问", test_frontend_assets_page)
    runner.test("Memory 页面可访问", test_frontend_memory_page)

    # 报告
    success = runner.report()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

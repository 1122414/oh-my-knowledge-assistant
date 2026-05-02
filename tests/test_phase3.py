"""Phase 3 功能测试脚本

测试飞书 Agent 任务执行通道的核心功能：
1. 权限服务（PermissionService）
2. ActionService（Source/Candidate/Knowledge/Config）
3. CommandRouter 新命令

运行方式：
    cd E:\GitHub\Repositories\oh-my-knowledge-assistant
    python tests/test_phase3.py

前置条件：
    - 后端服务已启动（或至少数据库已初始化）
    - .env 中配置了基本参数
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from omka.app.core.settings_service import set_setting
from omka.app.services.action_service import (
    ActionService,
    CandidateActionService,
    ConfigActionService,
    KnowledgeActionService,
    PermissionService,
    SourceActionService,
)
from omka.app.storage.db import get_session, init_db


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def test(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            print(f"  ❌ {name} | {detail}")

    def summary(self) -> None:
        print(f"\n{'=' * 50}")
        print(f"测试完成 | 通过: {self.passed} | 失败: {self.failed}")
        print(f"{'=' * 50}")


def test_permission_service(runner: TestRunner) -> None:
    print("\n📋 测试 PermissionService")

    # 设置测试权限
    set_setting("feishu_admin_open_ids", "admin_user_1,admin_user_2")
    set_setting("feishu_operator_open_ids", "operator_user_1")

    # 测试权限级别获取
    runner.test(
        "admin 用户识别",
        PermissionService.get_user_level("admin_user_1") == "admin",
        f"期望 admin, 实际 {PermissionService.get_user_level('admin_user_1')}"
    )
    runner.test(
        "operator 用户识别",
        PermissionService.get_user_level("operator_user_1") == "operator",
        f"期望 operator, 实际 {PermissionService.get_user_level('operator_user_1')}"
    )
    runner.test(
        "普通用户识别为 viewer",
        PermissionService.get_user_level("random_user") == "viewer",
        f"期望 viewer, 实际 {PermissionService.get_user_level('random_user')}"
    )

    # 测试权限检查
    runner.test(
        "admin 拥有所有权限",
        PermissionService.check_permission("admin_user_1", "admin"),
        "admin 应通过 admin 级别检查"
    )
    runner.test(
        "operator 拥有 operator 权限",
        PermissionService.check_permission("operator_user_1", "operator"),
        "operator 应通过 operator 级别检查"
    )
    runner.test(
        "operator 不拥有 admin 权限",
        not PermissionService.check_permission("operator_user_1", "admin"),
        "operator 不应通过 admin 级别检查"
    )
    runner.test(
        "viewer 只有 viewer 权限",
        PermissionService.check_permission("random_user", "viewer"),
        "viewer 应通过 viewer 级别检查"
    )
    runner.test(
        "viewer 不拥有 operator 权限",
        not PermissionService.check_permission("random_user", "operator"),
        "viewer 不应通过 operator 级别检查"
    )


def test_source_action_service(runner: TestRunner) -> None:
    print("\n📡 测试 SourceActionService")

    # 创建测试源
    source = SourceActionService.create_source(
        source_id="test_phase3_repo",
        name="Test Repo",
        source_type="github",
        mode="repo",
        repo_full_name="test/phase3",
    )
    runner.test("创建信息源", source.id == "test_phase3_repo", f"ID 不匹配: {source.id}")

    # 列表查询
    sources = SourceActionService.list_sources()
    runner.test("信息源列表查询", len(sources) >= 1, "列表为空")

    # 获取单个
    found = SourceActionService.get_source("test_phase3_repo")
    runner.test("获取信息源", found is not None and found.name == "Test Repo", "未找到信息源")

    # 停用
    ok = SourceActionService.set_source_enabled("test_phase3_repo", False)
    runner.test("停用信息源", ok, "停用失败")
    found = SourceActionService.get_source("test_phase3_repo")
    runner.test("停用后状态", found is not None and not found.enabled, "状态未更新")

    # 启用
    ok = SourceActionService.set_source_enabled("test_phase3_repo", True)
    runner.test("启用信息源", ok, "启用失败")

    # 删除
    ok = SourceActionService.delete_source("test_phase3_repo")
    runner.test("删除信息源", ok, "删除失败")
    found = SourceActionService.get_source("test_phase3_repo")
    runner.test("删除后不存在", found is None, "信息源仍存在")


def test_candidate_action_service(runner: TestRunner) -> None:
    print("\n📋 测试 CandidateActionService")

    # 先创建一个候选（需要数据库中有候选）
    from omka.app.storage.db import CandidateItem

    with get_session() as session:
        candidate = CandidateItem(
            id="test_candidate_001",
            normalized_item_id="norm_001",
            title="Test Candidate for Phase 3",
            url="https://github.com/test/phase3",
            item_type="repo",
            score=0.95,
            status="pending",
        )
        session.add(candidate)
        session.commit()

    # 列表查询
    candidates = CandidateActionService.list_candidates(status="pending", limit=10)
    runner.test("候选列表查询", len(candidates) >= 1, "列表为空")

    # 获取单个
    found = CandidateActionService.get_candidate("test_candidate_001")
    runner.test("获取候选", found is not None, "未找到候选")

    # 稍后读
    ok = CandidateActionService.read_later_candidate("test_candidate_001")
    runner.test("标记稍后读", ok, "标记失败")
    found = CandidateActionService.get_candidate("test_candidate_001")
    runner.test("稍后读状态", found is not None and found.status == "read_later", "状态未更新")

    # 重置为 pending 再测试 ignore
    with get_session() as session:
        found = session.get(CandidateItem, "test_candidate_001")
        if found:
            found.status = "pending"
            session.add(found)
            session.commit()

    ok = CandidateActionService.ignore_candidate("test_candidate_001")
    runner.test("忽略候选", ok, "忽略失败")
    found = CandidateActionService.get_candidate("test_candidate_001")
    runner.test("忽略状态", found is not None and found.status == "ignored", "状态未更新")

    # 清理
    with get_session() as session:
        found = session.get(CandidateItem, "test_candidate_001")
        if found:
            session.delete(found)
            session.commit()


def test_config_action_service(runner: TestRunner) -> None:
    print("\n⚙️ 测试 ConfigActionService")

    # 列表查询
    configs = ConfigActionService.list_config(mask_secrets=True)
    runner.test("配置列表查询", len(configs) > 0, "列表为空")

    # 获取配置
    value = ConfigActionService.get_config("app_name")
    runner.test("获取配置", value is not None, "未获取到值")

    # 敏感配置检查
    runner.test(
        "github_token 为敏感配置",
        ConfigActionService.is_sensitive("github_token"),
        "应识别为敏感配置"
    )
    runner.test(
        "app_name 不是敏感配置",
        not ConfigActionService.is_sensitive("app_name"),
        "不应识别为敏感配置"
    )

    # 修改非敏感配置
    success, message = ConfigActionService.set_config("feishu_command_prefix", "/test")
    runner.test("修改非敏感配置", success, message)

    # 验证修改
    value = ConfigActionService.get_config("feishu_command_prefix")
    runner.test("配置已更新", value == "/test", f"值不匹配: {value}")

    # 恢复默认值
    ConfigActionService.set_config("feishu_command_prefix", "/omka")

    # 尝试修改敏感配置
    success, message = ConfigActionService.set_config("github_token", "leaked")
    runner.test("禁止修改敏感配置", not success, "应拒绝修改敏感配置")


def test_knowledge_action_service(runner: TestRunner) -> None:
    print("\n📚 测试 KnowledgeActionService")

    # 先创建知识条目
    from omka.app.storage.db import KnowledgeItem

    with get_session() as session:
        item = KnowledgeItem(
            id="test_knowledge_001",
            candidate_item_id="candidate_001",
            title="Test Knowledge for Phase 3",
            url="https://github.com/test/phase3",
            item_type="repo",
            content="This is a test knowledge item for Phase 3 testing.",
        )
        session.add(item)
        session.commit()

    # 列表查询
    items = KnowledgeActionService.list_knowledge(limit=10)
    runner.test("知识库列表查询", len(items) >= 1, "列表为空")

    # 搜索
    results = KnowledgeActionService.search_knowledge("Phase 3", limit=10)
    runner.test("知识库搜索", len(results) >= 1, "搜索结果为空")

    # 删除
    ok = KnowledgeActionService.delete_knowledge("test_knowledge_001")
    runner.test("删除知识条目", ok, "删除失败")
    found = None
    with get_session() as session:
        found = session.get(KnowledgeItem, "test_knowledge_001")
    runner.test("删除后不存在", found is None, "知识条目仍存在")


def test_action_service_audit(runner: TestRunner) -> None:
    print("\n📋 测试 ActionService 审计")

    action = ActionService.create_action(
        action_type="test.audit",
        actor_channel="test",
        actor_external_id="test_user",
        target_type="test",
        target_id="test_target",
        request_text="test action",
        params_json={"key": "value"},
    )
    runner.test("创建审计记录", action.id > 0, "ID 无效")
    runner.test("审计记录初始状态", action.status == "pending", f"状态: {action.status}")

    ActionService.complete_action(action.id, "success", result_json={"ok": True})

    # 验证状态更新
    from omka.app.storage.db import SystemAction
    with get_session() as session:
        updated = session.get(SystemAction, action.id)
        runner.test("审计记录完成", updated is not None and updated.status == "success", "状态未更新")


def main() -> None:
    print("=" * 50)
    print("Phase 3 功能测试")
    print("=" * 50)

    # 初始化数据库
    init_db()

    runner = TestRunner()

    try:
        test_permission_service(runner)
    except Exception as e:
        print(f"  ❌ PermissionService 测试异常: {e}")
        runner.failed += 1

    try:
        test_source_action_service(runner)
    except Exception as e:
        print(f"  ❌ SourceActionService 测试异常: {e}")
        runner.failed += 1

    try:
        test_candidate_action_service(runner)
    except Exception as e:
        print(f"  ❌ CandidateActionService 测试异常: {e}")
        runner.failed += 1

    try:
        test_config_action_service(runner)
    except Exception as e:
        print(f"  ❌ ConfigActionService 测试异常: {e}")
        runner.failed += 1

    try:
        test_knowledge_action_service(runner)
    except Exception as e:
        print(f"  ❌ KnowledgeActionService 测试异常: {e}")
        runner.failed += 1

    try:
        test_action_service_audit(runner)
    except Exception as e:
        print(f"  ❌ ActionService 审计测试异常: {e}")
        runner.failed += 1

    runner.summary()

    if runner.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

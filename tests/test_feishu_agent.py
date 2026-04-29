"""飞书 Agent 集成测试脚本

测试飞书应用机器人 + SimpleKnowledgeAgent 集成功能。

使用方法:
1. 确保后端服务已启动: python -m omka.app.main
2. 确保 .env 中已配置飞书凭证和 Agent 配置
3. 运行测试: python tests/test_feishu_agent.py
"""

import asyncio
import sys

import httpx

BASE_URL = "http://127.0.0.1:8000"


async def test_health():
    print("\n=== 测试健康检查 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 服务正常: {data}")
            return True
        else:
            print(f"✗ 服务异常: HTTP {response.status_code}")
            return False


async def test_feishu_status():
    print("\n=== 测试飞书状态 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/integrations/feishu/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 飞书状态:")
            print(f"  - 启用: {data.get('enabled')}")
            print(f"  - 已配置: {data.get('configured')}")
            print(f"  - Agent 启用: {data.get('agent_enabled')}")
            print(f"  - 绑定用户: {data.get('bound_users')}")
            return True
        else:
            print(f"✗ 获取状态失败: HTTP {response.status_code}")
            return False


async def test_feishu_credentials():
    print("\n=== 测试飞书凭证 ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/integrations/feishu/test-credentials")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✓ 凭证验证成功: {data.get('message')}")
            else:
                print(f"✗ 凭证验证失败: {data.get('message')}")
            return data.get("success", False)
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            return False


async def test_feishu_send_test():
    print("\n=== 测试飞书发送测试消息 ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/integrations/feishu/send-test")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✓ 测试消息发送成功: {data.get('message')}")
            else:
                print(f"✗ 测试消息发送失败: {data.get('message')}")
            return data.get("success", False)
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            return False


async def test_feishu_conversations():
    print("\n=== 测试飞书绑定用户列表 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/integrations/feishu/conversations")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 绑定用户: {len(data)} 个")
            for conv in data[:5]:
                print(f"  - open_id: {conv.get('open_id')} | enabled: {conv.get('enabled')}")
            return True
        else:
            print(f"✗ 获取列表失败: HTTP {response.status_code}")
            return False


async def test_agent():
    print("\n=== 测试 Agent 对话 ===")
    async with httpx.AsyncClient() as client:
        payload = {"message": "今天有什么 AI Agent 项目值得关注？"}
        response = await client.post(f"{BASE_URL}/agent/test", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Agent 状态: {data.get('status')}")
            print(f"  - 回答: {data.get('answer', '')[:200]}...")
            print(f"  - 使用上下文: {data.get('used_context')}")
            print(f"  - 建议动作: {data.get('suggested_actions')}")
            return data.get("status") == "success"
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            return False


async def test_agent_disabled():
    print("\n=== 测试 Agent 未启用 ===")
    async with httpx.AsyncClient() as client:
        payload = {"message": "测试消息"}
        response = await client.post(f"{BASE_URL}/agent/test", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Agent 状态: {data.get('status')}")
            print(f"  - 回答: {data.get('answer')}")
            return data.get("status") == "disabled"
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            return False


async def test_feishu_event_logs():
    print("\n=== 测试飞书事件日志 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/integrations/feishu/event-logs")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 事件日志: {len(data)} 条")
            for log in data[:5]:
                print(f"  - [{log.get('handled_status')}] {log.get('event_type')}")
            return True
        else:
            print(f"✗ 获取日志失败: HTTP {response.status_code}")
            return False


async def test_feishu_message_runs():
    print("\n=== 测试飞书消息发送记录 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/integrations/feishu/message-runs")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 消息记录: {len(data)} 条")
            for run in data[:5]:
                print(f"  - [{run.get('status')}] {run.get('message_type')} -> {run.get('receive_id_masked')}")
            return True
        else:
            print(f"✗ 获取记录失败: HTTP {response.status_code}")
            return False


async def main():
    print("=" * 60)
    print("OMKA 飞书 Agent 集成测试")
    print("=" * 60)

    results = []

    results.append(("健康检查", await test_health()))

    if results[-1][1]:
        results.append(("飞书状态", await test_feishu_status()))
        results.append(("飞书凭证", await test_feishu_credentials()))
        results.append(("绑定用户", await test_feishu_conversations()))
        results.append(("事件日志", await test_feishu_event_logs()))
        results.append(("消息记录", await test_feishu_message_runs()))
        results.append(("测试消息", await test_feishu_send_test()))
        results.append(("Agent 对话", await test_agent()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status} | {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n所有测试通过！")
        return 0
    else:
        print("\n部分测试失败，请检查配置和服务状态。")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

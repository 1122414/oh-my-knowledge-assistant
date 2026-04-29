"""飞书集成功能测试脚本

测试飞书应用机器人集成的各项功能。

使用方法:
1. 确保后端服务已启动: python -m omka.app.main
2. 确保 .env 中已配置飞书凭证
3. 运行测试: python tests/test_feishu_integration.py
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


async def test_settings_api():
    print("\n=== 测试配置 API ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/settings")
        if response.status_code == 200:
            data = response.json()
            settings = data.get("settings", {})
            feishu_keys = [k for k in settings.keys() if k.startswith("feishu_")]
            print(f"✓ 获取配置成功，飞书相关配置 {len(feishu_keys)} 项")
            for key in sorted(feishu_keys):
                print(f"  - {key}: {settings[key]}")
            return True
        else:
            print(f"✗ 获取配置失败: HTTP {response.status_code}")
            return False


async def test_feishu_send_test():
    print("\n=== 测试飞书测试消息发送 ===")
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


async def test_feishu_send_latest_digest():
    print("\n=== 测试飞书发送最新简报 ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/integrations/feishu/send-latest-digest")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✓ 最新简报发送成功: {data.get('message')}")
            else:
                print(f"✗ 最新简报发送失败: {data.get('message')}")
            return data.get("success", False)
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            return False


async def test_feishu_message_runs():
    print("\n=== 测试飞书消息发送记录 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/integrations/feishu/message-runs")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取消息记录成功，共 {len(data)} 条")
            for run in data[:5]:
                print(f"  - [{run.get('status')}] {run.get('message_type')} -> {run.get('receive_id_masked')}")
            return True
        else:
            print(f"✗ 获取消息记录失败: HTTP {response.status_code}")
            return False


async def test_feishu_event_logs():
    print("\n=== 测试飞书事件日志 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/integrations/feishu/event-logs")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取事件日志成功，共 {len(data)} 条")
            for log in data[:5]:
                print(f"  - [{log.get('handled_status')}] {log.get('event_type')}")
            return True
        else:
            print(f"✗ 获取事件日志失败: HTTP {response.status_code}")
            return False


async def test_feishu_challenge():
    print("\n=== 测试飞书事件回调 Challenge ===")
    async with httpx.AsyncClient() as client:
        payload = {
            "schema": "2.0",
            "header": {
                "event_id": "test_event_001",
                "event_type": "url_verification",
                "token": "test_token",
            },
            "challenge": "test_challenge_value",
            "token": "test_token",
            "type": "url_verification",
        }
        response = await client.post(
            f"{BASE_URL}/integrations/feishu/events",
            json=payload,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("challenge") == "test_challenge_value":
                print(f"✓ Challenge 验证成功")
                return True
            else:
                print(f"✗ Challenge 验证失败: {data}")
                return False
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            return False


async def main():
    print("=" * 60)
    print("OMKA 飞书集成功能测试")
    print("=" * 60)

    results = []

    results.append(("健康检查", await test_health()))

    if results[-1][1]:
        results.append(("配置 API", await test_settings_api()))
        results.append(("消息记录", await test_feishu_message_runs()))
        results.append(("事件日志", await test_feishu_event_logs()))
        results.append(("Challenge", await test_feishu_challenge()))
        results.append(("测试消息", await test_feishu_send_test()))
        results.append(("最新简报", await test_feishu_send_latest_digest()))

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

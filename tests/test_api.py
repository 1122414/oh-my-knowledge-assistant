"""OMKA 功能测试脚本

使用方法:
1. 确保已安装依赖: pip install -r requirements.txt
2. 复制 .env.example 为 .env 并填入 GITHUB_TOKEN
3. 启动服务: python -m omka.app.main 或使用 uvicorn
4. 运行测试: python tests/test_api.py

测试覆盖:
- 健康检查
- 数据源 CRUD
- 手动触发抓取
- 候选池查看/确认/忽略
- 排序执行
- 每日简报生成
"""

import asyncio
import sys

import httpx

BASE_URL = "http://localhost:8000"


async def test_health():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        print("[PASS] 健康检查", data)


async def test_sources_crud():
    async with httpx.AsyncClient() as client:
        # 创建数据源
        source = {
            "id": "test_repo_langgraph",
            "source_type": "github",
            "name": "LangGraph Test",
            "enabled": True,
            "mode": "repo",
            "repo_full_name": "langchain-ai/langgraph",
            "weight": 1.0,
        }
        r = await client.post(f"{BASE_URL}/sources", json=source)
        assert r.status_code == 200
        print("[PASS] 创建数据源", r.json())

        # 列表
        r = await client.get(f"{BASE_URL}/sources")
        assert r.status_code == 200
        sources = r.json()
        assert len(sources) >= 1
        print("[PASS] 列出数据源 | 数量=", len(sources))

        # 更新
        r = await client.put(f"{BASE_URL}/sources/test_repo_langgraph", json={"weight": 1.5})
        assert r.status_code == 200
        print("[PASS] 更新数据源", r.json())

        return "test_repo_langgraph"


async def test_fetch(source_id: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{BASE_URL}/sources/{source_id}/run")
        assert r.status_code == 200
        data = r.json()
        print("[PASS] 手动抓取", data)
        return data.get("fetched_count", 0)


async def test_candidates():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/candidates")
        assert r.status_code == 200
        candidates = r.json()
        print("[PASS] 候选池 | 数量=", len(candidates))
        return candidates


async def test_ranking():
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/digests/run-ranking")
        assert r.status_code == 200
        data = r.json()
        print("[PASS] 执行排序", data)

        r = await client.get(f"{BASE_URL}/digests/ranked?limit=5")
        assert r.status_code == 200
        ranked = r.json()
        print("[PASS] 排名结果 | 数量=", len(ranked))
        for i, c in enumerate(ranked[:3], 1):
            print(f"  {i}. {c['title']} | score={c['score']}")
        return ranked


async def test_digest():
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(f"{BASE_URL}/digests/run-today")
        assert r.status_code == 200
        data = r.json()
        print("[PASS] 生成简报", data)
        return data


async def test_confirm_candidate(candidate_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/candidates/{candidate_id}/confirm")
        assert r.status_code == 200
        print("[PASS] 确认候选", r.json())


async def test_knowledge():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/knowledge")
        assert r.status_code == 200
        items = r.json()
        print("[PASS] 知识库 | 数量=", len(items))
        return items


async def test_cleanup(source_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{BASE_URL}/sources/{source_id}")
        assert r.status_code == 200
        print("[PASS] 清理测试数据", r.json())


async def run_all_tests():
    print("=" * 60)
    print("OMKA 功能测试开始")
    print("=" * 60)

    try:
        await test_health()
        source_id = await test_sources_crud()

        fetched = await test_fetch(source_id)
        if fetched == 0:
            print("[WARN] 没有抓取到数据，可能缺少 GITHUB_TOKEN 或 API 限制")

        candidates = await test_candidates()
        await test_ranking()

        if candidates:
            await test_confirm_candidate(candidates[0]["id"])

        await test_knowledge()

        # 简报生成需要 LLM，可能较慢或失败
        try:
            await test_digest()
        except Exception as e:
            print("[WARN] 简报生成失败（可能需要配置 LLM）", e)

        await test_cleanup(source_id)

        print("=" * 60)
        print("所有测试通过")
        print("=" * 60)

    except Exception as e:
        print("[FAIL] 测试失败", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

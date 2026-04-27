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
from urllib.parse import quote

import httpx

# =============================================================================
# 测试常量配置 - 修改以下值即可自定义测试行为
# =============================================================================

# API 服务地址
BASE_URL = "http://localhost:8000"

# 测试数据源配置
TEST_SOURCE_ID = "test_repo_langgraph"
TEST_SOURCE_TYPE = "github"
TEST_SOURCE_NAME = "LangGraph Test"
TEST_REPO_FULL_NAME = "langchain-ai/langgraph"
TEST_SOURCE_WEIGHT = 1.0
TEST_SOURCE_MODE = "repo"  # "repo" 或 "search"
TEST_SOURCE_ENABLED = True

# HTTP 超时配置（秒）
FETCH_TIMEOUT = 60.0       # 抓取请求超时
DIGEST_TIMEOUT = 120.0     # 简报生成超时（可能涉及 LLM 调用）
DEFAULT_TIMEOUT = 30.0     # 默认请求超时

# 测试数据限制
RANKED_LIMIT = 5           # 查看排名结果数量
RANKED_PREVIEW_COUNT = 3   # 预览排名结果数量

# =============================================================================
# 测试实现
# =============================================================================


async def test_health():
    """测试健康检查端点.

    验证服务是否正常运行，返回状态码 200 且 status 为 ok.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        print("[PASS] 健康检查", data)


async def test_sources_crud():
    """测试数据源 CRUD 操作.

    依次执行创建、列表查询、更新操作，验证数据源管理功能.

    Returns:
        str: 创建的数据源 ID，供后续测试使用.
    """
    async with httpx.AsyncClient() as client:
        source = {
            "id": TEST_SOURCE_ID,
            "source_type": TEST_SOURCE_TYPE,
            "name": TEST_SOURCE_NAME,
            "enabled": TEST_SOURCE_ENABLED,
            "mode": TEST_SOURCE_MODE,
            "repo_full_name": TEST_REPO_FULL_NAME,
            "weight": TEST_SOURCE_WEIGHT,
        }
        r = await client.post(f"{BASE_URL}/sources", json=source)
        assert r.status_code == 200
        print("[PASS] 创建数据源", r.json())

        r = await client.get(f"{BASE_URL}/sources")
        assert r.status_code == 200
        sources = r.json()
        assert len(sources) >= 1
        print("[PASS] 列出数据源 | 数量=", len(sources))

        r = await client.put(f"{BASE_URL}/sources/{TEST_SOURCE_ID}", json={"weight": 1.5})
        assert r.status_code == 200
        print("[PASS] 更新数据源", r.json())

        return TEST_SOURCE_ID


async def test_fetch(source_id: str) -> int:
    """触发指定数据源的手动抓取.

    Args:
        source_id: 要抓取的数据源 ID.

    Returns:
        int: 实际抓取到的条目数量，0 表示未获取到数据.
    """
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
        r = await client.post(f"{BASE_URL}/sources/{source_id}/run")
        assert r.status_code == 200
        data = r.json()
        print("[PASS] 手动抓取", data)
        return data.get("fetched_count", 0)


async def test_candidates():
    """查询当前候选池中的所有条目.

    Returns:
        list[dict]: 候选条目列表，每个条目包含 id、title、score 等字段.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/candidates")
        assert r.status_code == 200
        candidates = r.json()
        print("[PASS] 候选池 | 数量=", len(candidates))
        return candidates


async def test_ranking():
    """执行排序并获取排名靠前的候选结果.

    先调用排序接口计算分数，再查询排名列表，打印前 N 条结果.

    Returns:
        list[dict]: 排序后的候选条目列表.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/digests/run-ranking")
        assert r.status_code == 200
        data = r.json()
        print("[PASS] 执行排序", data)

        r = await client.get(f"{BASE_URL}/digests/ranked?limit={RANKED_LIMIT}")
        assert r.status_code == 200
        ranked = r.json()
        print("[PASS] 排名结果 | 数量=", len(ranked))
        for i, c in enumerate(ranked[:RANKED_PREVIEW_COUNT], 1):
            print(f"  {i}. {c['title']} | score={c['score']}")
        return ranked


async def test_digest():
    """生成今日的每日简报.

    调用完整的日报生成流程，可能涉及 LLM 总结，耗时较长.

    Returns:
        dict: 简报生成结果，包含输出文件路径等信息.
    """
    async with httpx.AsyncClient(timeout=DIGEST_TIMEOUT) as client:
        r = await client.post(f"{BASE_URL}/digests/run-today")
        assert r.status_code == 200
        data = r.json()
        print("[PASS] 生成简报", data)
        return data


async def test_confirm_candidate(candidate_id: str):
    """将指定候选条目确认为知识库条目.

    Args:
        candidate_id: 要确认的候选条目 ID.
    """
    async with httpx.AsyncClient() as client:
        encoded_id = quote(candidate_id, safe="")
        r = await client.post(f"{BASE_URL}/candidates/{encoded_id}/confirm")
        assert r.status_code == 200
        print("[PASS] 确认候选", r.json())


async def test_knowledge():
    """查询当前知识库中的所有已确认条目.

    Returns:
        list[dict]: 知识库条目列表.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/knowledge")
        assert r.status_code == 200
        items = r.json()
        print("[PASS] 知识库 | 数量=", len(items))
        return items


async def test_cleanup(source_id: str):
    """清理测试过程中产生的数据.

    删除测试数据源及由候选条目转换而来的知识库条目，避免污染正式数据.

    Args:
        source_id: 要删除的测试数据源 ID.
    """
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{BASE_URL}/sources/{source_id}")
        assert r.status_code == 200
        print("[PASS] 清理测试数据源", r.json())

        r = await client.get(f"{BASE_URL}/knowledge")
        if r.status_code == 200:
            for item in r.json():
                if item["id"].startswith("knowledge:candidate:"):
                    await client.delete(f"{BASE_URL}/knowledge/{item['id']}")


async def run_all_tests():
    """按顺序执行所有测试用例.

    编排完整测试流程：健康检查 → 数据源 CRUD → 抓取 → 候选池 → 排序 →
    确认候选 → 知识库 → 简报生成 → 清理。任何步骤失败都会终止并打印堆栈.
    """
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

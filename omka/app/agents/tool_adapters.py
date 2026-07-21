"""Adapters exposing OMKA domain actions as Agent tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import func, select

from omka.app.agents.tools import AgentTool, ToolContext, ToolRegistry
from omka.app.services.action_service import (
    CandidateActionService,
    SourceActionService,
)
from omka.app.services.memory_service import MemoryService
from omka.app.services.recommendation_service import RecommendationService
from omka.app.storage.db import (
    CandidateItem,
    FetchRun,
    KnowledgeItem,
    get_session,
)


class EmptyArgs(BaseModel):
    pass


class LimitArgs(BaseModel):
    limit: int = Field(default=10, ge=1, le=30)


class KnowledgeSearchArgs(LimitArgs):
    query: str = Field(min_length=1, max_length=200)


class CandidateListArgs(LimitArgs):
    status: str = Field(default="pending", pattern="^(pending|confirmed|ignored|read_later)$")


class CandidateActionArgs(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=300)


class SourceListArgs(BaseModel):
    enabled_only: bool = False


class SourceAddRepoArgs(BaseModel):
    repo_full_name: str = Field(
        min_length=3,
        max_length=200,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    name: str | None = Field(default=None, max_length=120)


class MemorySearchArgs(LimitArgs):
    query: str = Field(default="", max_length=200)


class MemoryAddArgs(BaseModel):
    content: str = Field(min_length=2, max_length=2000)
    subject: str = Field(default="preference", max_length=80)


class RecommendationExplainArgs(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=300)


def _serialize_models(items: list[Any]) -> list[dict[str, Any]]:
    return [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
        for item in items
    ]


def _system_status(_args: EmptyArgs, _context: ToolContext) -> dict[str, Any]:
    with get_session() as session:
        latest_run = session.exec(
            select(FetchRun).order_by(FetchRun.started_at.desc())
        ).first()
        pending_count = session.exec(
            select(func.count(CandidateItem.id)).where(CandidateItem.status == "pending")
        ).one()
        knowledge_count = session.exec(select(func.count(KnowledgeItem.id))).one()
    return {
        "message": "已读取 OMKA 当前运行状态",
        "latest_run": latest_run.model_dump(mode="json") if latest_run else None,
        "pending_candidates": pending_count,
        "knowledge_count": knowledge_count,
    }


def _search_knowledge(args: KnowledgeSearchArgs, _context: ToolContext) -> dict[str, Any]:
    items = SourceKnowledgeAdapter.search(args.query, args.limit)
    return {
        "message": f"知识库中找到 {len(items)} 条相关内容",
        "items": _serialize_models(items),
    }


class SourceKnowledgeAdapter:
    """Keeps the storage-backed knowledge lookup behind one adapter."""

    @staticmethod
    def search(query: str, limit: int) -> list[KnowledgeItem]:
        from omka.app.services.action_service import KnowledgeActionService

        return KnowledgeActionService.search_knowledge(query, limit=limit)


def _list_candidates(args: CandidateListArgs, _context: ToolContext) -> dict[str, Any]:
    items = CandidateActionService.list_candidates(status=args.status, limit=args.limit)
    return {
        "message": f"找到 {len(items)} 条 {args.status} 候选内容",
        "items": _serialize_models(items),
    }


def _save_candidate(args: CandidateActionArgs, _context: ToolContext) -> dict[str, Any]:
    success = CandidateActionService.confirm_candidate(args.candidate_id)
    if not success:
        raise ValueError(f"候选内容不存在: {args.candidate_id}")
    return {"message": "候选内容已收藏到知识库", "candidate_id": args.candidate_id}


def _ignore_candidate(args: CandidateActionArgs, _context: ToolContext) -> dict[str, Any]:
    success = CandidateActionService.ignore_candidate(args.candidate_id)
    if not success:
        raise ValueError(f"候选内容不存在: {args.candidate_id}")
    return {"message": "候选内容已忽略", "candidate_id": args.candidate_id}


def _read_later_candidate(args: CandidateActionArgs, _context: ToolContext) -> dict[str, Any]:
    success = CandidateActionService.read_later_candidate(args.candidate_id)
    if not success:
        raise ValueError(f"候选内容不存在: {args.candidate_id}")
    return {"message": "候选内容已加入稍后阅读", "candidate_id": args.candidate_id}


def _list_sources(args: SourceListArgs, _context: ToolContext) -> dict[str, Any]:
    sources = SourceActionService.list_sources(enabled_only=args.enabled_only)
    return {
        "message": f"找到 {len(sources)} 个信息源",
        "items": _serialize_models(sources),
    }


def _add_repo_source(args: SourceAddRepoArgs, _context: ToolContext) -> dict[str, Any]:
    repo = args.repo_full_name
    source_id = f"src_github_{repo.replace('/', '_')}"
    source = SourceActionService.create_source(
        source_id=source_id,
        name=args.name or repo.split("/", 1)[1],
        source_type="github",
        mode="repo",
        repo_full_name=repo,
    )
    return {
        "message": f"已添加 GitHub 信息源 {repo}",
        "source": source.model_dump(mode="json"),
    }


def _search_memories(args: MemorySearchArgs, context: ToolContext) -> dict[str, Any]:
    memories = MemoryService.get_active_memories_for_context(
        owner_external_id=context.actor_external_id,
        conversation_id=context.conversation_id,
        query_text=args.query,
        max_items=args.limit,
    )
    return {
        "message": f"找到 {len(memories)} 条相关记忆",
        "items": _serialize_models(memories),
    }


def _add_memory(args: MemoryAddArgs, context: ToolContext) -> dict[str, Any]:
    memory = MemoryService.create_memory(
        memory_type="user",
        subject=args.subject,
        content=args.content,
        scope="user",
        owner_external_id=context.actor_external_id,
        source_type="conversation",
        source_ref=context.conversation_id,
        actor_type="agent",
        actor_id=context.actor_external_id,
    )
    return {
        "message": "已保存为用户记忆",
        "memory": memory.model_dump(mode="json"),
    }


def _explain_recommendation(
    args: RecommendationExplainArgs,
    _context: ToolContext,
) -> dict[str, Any]:
    explanation = RecommendationService.get_explanation(args.candidate_id)
    if not explanation:
        raise ValueError(f"没有找到候选内容的推荐解释: {args.candidate_id}")
    return {"message": "已读取推荐原因", "explanation": explanation}


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="system.status",
            description="查看最近任务运行、待处理候选和知识库数量",
            args_model=EmptyArgs,
            handler=_system_status,
        )
    )
    registry.register(
        AgentTool(
            name="knowledge.search",
            description="按关键词搜索已经收藏的知识内容",
            args_model=KnowledgeSearchArgs,
            handler=_search_knowledge,
        )
    )
    registry.register(
        AgentTool(
            name="candidate.list",
            description="查看待处理、已收藏、已忽略或稍后阅读的候选内容",
            args_model=CandidateListArgs,
            handler=_list_candidates,
        )
    )
    registry.register(
        AgentTool(
            name="candidate.save",
            description="把指定候选内容收藏到知识库",
            args_model=CandidateActionArgs,
            handler=_save_candidate,
            risk="write",
            required_level="operator",
        )
    )
    registry.register(
        AgentTool(
            name="candidate.ignore",
            description="忽略指定候选内容；执行前必须确认",
            args_model=CandidateActionArgs,
            handler=_ignore_candidate,
            risk="destructive",
            required_level="operator",
            requires_confirmation=True,
        )
    )
    registry.register(
        AgentTool(
            name="candidate.read_later",
            description="把指定候选内容加入稍后阅读",
            args_model=CandidateActionArgs,
            handler=_read_later_candidate,
            risk="write",
            required_level="operator",
        )
    )
    registry.register(
        AgentTool(
            name="source.list",
            description="查看已配置的 GitHub 信息源",
            args_model=SourceListArgs,
            handler=_list_sources,
        )
    )
    registry.register(
        AgentTool(
            name="source.add_repo",
            description="添加一个 GitHub 仓库信息源；执行前必须确认",
            args_model=SourceAddRepoArgs,
            handler=_add_repo_source,
            risk="write",
            required_level="operator",
            requires_confirmation=True,
        )
    )
    registry.register(
        AgentTool(
            name="memory.search",
            description="搜索当前用户和会话可见的长期记忆",
            args_model=MemorySearchArgs,
            handler=_search_memories,
        )
    )
    registry.register(
        AgentTool(
            name="memory.add",
            description="保存一条属于当前用户的长期记忆",
            args_model=MemoryAddArgs,
            handler=_add_memory,
            risk="write",
        )
    )
    registry.register(
        AgentTool(
            name="recommendation.explain",
            description="解释某条候选内容为什么被推荐",
            args_model=RecommendationExplainArgs,
            handler=_explain_recommendation,
        )
    )
    return registry


_default_registry: ToolRegistry | None = None


def get_default_tool_registry() -> ToolRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_tool_registry()
    return _default_registry

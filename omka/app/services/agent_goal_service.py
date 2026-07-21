"""Persistence and scheduling for bounded proactive Agent goals."""

from __future__ import annotations

import uuid
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import update
from sqlmodel import col, select

from omka.app.agents.context_builder import ContextBuilder
from omka.app.agents.runtime import KnowledgeAgentRuntime
from omka.app.agents.tool_adapters import get_default_tool_registry
from omka.app.core.config import settings
from omka.app.core.logging import get_logger
from omka.app.core.scheduler import get_scheduler
from omka.app.services.scheduler_service import validate_cron
from omka.app.storage.db import AgentGoal, ConversationMessage, get_session

logger = get_logger("agent")

DEFAULT_PROACTIVE_TOOLS = [
    "system.status",
    "knowledge.search",
    "candidate.list",
    "source.list",
    "memory.search",
    "recommendation.explain",
]


class AgentGoalService:
    @staticmethod
    def create_goal(
        *,
        owner_external_id: str,
        conversation_id: str,
        objective: str,
        schedule_cron: str | None = None,
        allowed_tools: list[str] | None = None,
        max_steps: int = 4,
    ) -> AgentGoal:
        if schedule_cron and not validate_cron(schedule_cron):
            raise ValueError(f"无效 Cron 表达式: {schedule_cron}")
        registry = get_default_tool_registry()
        requested_tools = allowed_tools or DEFAULT_PROACTIVE_TOOLS
        unknown = [name for name in requested_tools if registry.get(name) is None]
        if unknown:
            raise ValueError(f"包含未知工具: {', '.join(unknown)}")

        goal = AgentGoal(
            id=f"goal_{uuid.uuid4().hex[:16]}",
            owner_external_id=owner_external_id,
            conversation_id=conversation_id,
            objective=objective.strip(),
            schedule_cron=schedule_cron,
            allowed_tools=requested_tools,
            max_steps=max(1, min(max_steps, 8)),
        )
        with get_session() as session:
            session.add(goal)
            session.commit()
            session.refresh(goal)
        if schedule_cron:
            AgentGoalService._schedule(goal)
        return goal

    @staticmethod
    def list_goals(
        *,
        owner_external_id: str | None = None,
        status: str | None = None,
    ) -> list[AgentGoal]:
        with get_session() as session:
            query = select(AgentGoal)
            if owner_external_id:
                query = query.where(AgentGoal.owner_external_id == owner_external_id)
            if status:
                query = query.where(AgentGoal.status == status)
            return list(
                session.exec(
                    query.order_by(col(AgentGoal.created_at).desc())
                ).all()
            )

    @staticmethod
    def get_goal(goal_id: str) -> AgentGoal | None:
        with get_session() as session:
            return session.get(AgentGoal, goal_id)

    @staticmethod
    def prepare_goal_run(goal_id: str) -> AgentGoal:
        with get_session() as session:
            goal = session.get(AgentGoal, goal_id)
            if not goal:
                raise ValueError(f"目标不存在: {goal_id}")
            if goal.status == "paused":
                raise ValueError("目标已暂停")
            claimed = session.exec(
                update(AgentGoal)
                .where(AgentGoal.id == goal_id)
                .where(AgentGoal.status.not_in(("paused", "running")))
                .values(
                    status="running",
                    last_error=None,
                    updated_at=datetime.utcnow(),
                )
            )
            session.commit()
            if claimed.rowcount != 1:
                current = session.get(AgentGoal, goal_id)
                if current:
                    return current
                raise ValueError(f"目标不存在: {goal_id}")
            goal = session.get(AgentGoal, goal_id)
            if not goal:
                raise ValueError(f"目标不存在: {goal_id}")

        try:
            run = KnowledgeAgentRuntime.create_pending_run(
                user_message=goal.objective,
                conversation_id=goal.conversation_id,
                user_external_id=goal.owner_external_id,
                channel="agent_goal",
            )
            if run.id is None:
                raise RuntimeError("Agent Goal Run 创建失败")
            with get_session() as session:
                stored = session.get(AgentGoal, goal_id)
                if not stored:
                    raise ValueError(f"目标已被删除: {goal_id}")
                stored.last_run_id = run.id
                stored.updated_at = datetime.utcnow()
                session.add(stored)
                session.commit()
                session.refresh(stored)
                return stored
        except Exception as exc:
            with get_session() as session:
                stored = session.get(AgentGoal, goal_id)
                if stored:
                    stored.status = "failed"
                    stored.last_error = str(exc)[:1000]
                    stored.updated_at = datetime.utcnow()
                    session.add(stored)
                    session.commit()
            raise

    @staticmethod
    async def run_goal(
        goal_id: str,
        *,
        prepared_run_id: int | None = None,
    ) -> AgentGoal:
        if prepared_run_id is None:
            goal = AgentGoalService.prepare_goal_run(goal_id)
            prepared_run_id = goal.last_run_id
        else:
            with get_session() as session:
                goal = session.get(AgentGoal, goal_id)
                if not goal:
                    raise ValueError(f"目标不存在: {goal_id}")
                if goal.status != "running":
                    raise ValueError(f"目标未处于运行状态: {goal.status}")
        if prepared_run_id is None:
            raise RuntimeError("Agent Goal 缺少关联 Run")

        try:
            context_builder = ContextBuilder(
                max_recent_messages=settings.omka_agent_max_recent_messages,
                max_digest_items=settings.omka_agent_max_digest_items,
                max_knowledge_items=settings.omka_agent_max_knowledge_items,
                max_candidate_items=settings.omka_agent_max_candidate_items,
                max_memory_items=settings.memory_max_active_items,
                max_context_chars=settings.omka_agent_max_context_chars,
            )
            registry = get_default_tool_registry().subset(goal.allowed_tools)
            response = await KnowledgeAgentRuntime(
                tool_registry=registry,
                max_steps=goal.max_steps,
            ).execute(
                user_message=goal.objective,
                conversation_id=goal.conversation_id,
                user_external_id=goal.owner_external_id,
                channel="agent_goal",
                context_builder=context_builder,
                run_id=prepared_run_id,
            )

            with get_session() as session:
                stored = session.get(AgentGoal, goal_id)
                if not stored:
                    raise ValueError(f"目标已被删除: {goal_id}")
                if response.status in {"success", "degraded", "step_limit"}:
                    stored.status = "active" if stored.schedule_cron else "completed"
                    if response.status != "success":
                        stored.last_error = f"Agent 以 {response.status} 状态完成"
                elif response.status == "needs_confirm":
                    stored.status = "paused"
                    stored.last_error = "目标已暂停，等待用户确认高风险操作"
                else:
                    stored.status = "failed"
                    stored.last_error = f"Agent 运行状态: {response.status}"
                stored.last_run_id = response.run_id
                stored.last_result_preview = response.answer[:500]
                stored.last_run_at = datetime.utcnow()
                stored.updated_at = datetime.utcnow()
                session.add(stored)
                session.add(
                    ConversationMessage(
                        channel="agent_goal",
                        conversation_id=stored.conversation_id,
                        user_external_id=stored.owner_external_id,
                        role="assistant",
                        content=response.answer,
                    )
                )
                session.commit()
                session.refresh(stored)
                return stored
        except Exception as exc:
            with get_session() as session:
                stored = session.get(AgentGoal, goal_id)
                if stored:
                    stored.status = "failed"
                    stored.last_error = str(exc)[:1000]
                    stored.last_run_at = datetime.utcnow()
                    stored.updated_at = datetime.utcnow()
                    session.add(stored)
                    session.commit()
                    session.refresh(stored)
                    logger.error("Agent 目标运行失败 | goal=%s | error=%s", goal_id, exc)
                    return stored
            raise

    @staticmethod
    def set_status(goal_id: str, status: str) -> AgentGoal | None:
        if status not in ("active", "paused"):
            raise ValueError("目标状态只能是 active 或 paused")
        with get_session() as session:
            goal = session.get(AgentGoal, goal_id)
            if not goal:
                return None
            goal.status = status
            goal.updated_at = datetime.utcnow()
            session.add(goal)
            session.commit()
            session.refresh(goal)
        scheduler = get_scheduler()
        job = scheduler.get_job(AgentGoalService._job_id(goal_id))
        if job:
            job.resume() if status == "active" else job.pause()
        elif status == "active" and goal.schedule_cron:
            AgentGoalService._schedule(goal)
        return goal

    @staticmethod
    def delete_goal(goal_id: str) -> bool:
        with get_session() as session:
            goal = session.get(AgentGoal, goal_id)
            if not goal:
                return False
            session.delete(goal)
            session.commit()
        scheduler = get_scheduler()
        job = scheduler.get_job(AgentGoalService._job_id(goal_id))
        if job:
            scheduler.remove_job(job.id)
        return True

    @staticmethod
    def restore_schedules() -> int:
        goals = AgentGoalService.list_goals(status="active")
        restored = 0
        for goal in goals:
            if goal.schedule_cron:
                AgentGoalService._schedule(goal)
                restored += 1
        logger.info("Agent 主动目标计划已恢复 | count=%d", restored)
        return restored

    @staticmethod
    def _schedule(goal: AgentGoal) -> None:
        if not goal.schedule_cron:
            return
        scheduler = get_scheduler()
        scheduler.add_job(
            run_agent_goal,
            trigger=CronTrigger.from_crontab(
                goal.schedule_cron,
                timezone=settings.scheduler_timezone,
            ),
            args=[goal.id],
            id=AgentGoalService._job_id(goal.id),
            name=f"Agent Goal: {goal.objective[:40]}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=1800,
        )

    @staticmethod
    def _job_id(goal_id: str) -> str:
        return f"agent_goal:{goal_id}"


async def run_agent_goal(goal_id: str) -> None:
    await AgentGoalService.run_goal(goal_id)

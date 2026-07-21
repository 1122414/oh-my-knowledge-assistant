"""Typed, permission-aware tools used by the Agent runtime."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from omka.app.core.logging import get_logger
from omka.app.services.action_service import ActionService, PermissionService
from omka.app.storage.db import SystemAction, get_session

logger = get_logger("agent")

ToolRisk = Literal["read", "write", "destructive"]
ToolStatus = Literal["success", "failed", "denied", "needs_confirm"]
ToolHandler = Callable[[BaseModel, "ToolContext"], dict[str, Any] | Awaitable[dict[str, Any]]]


class ToolContext(BaseModel):
    actor_channel: str = "agent"
    actor_external_id: str
    conversation_id: str


class ToolResult(BaseModel):
    tool_name: str
    status: ToolStatus
    content: str
    data: dict[str, Any] = Field(default_factory=dict)
    confirmation_id: int | None = None
    error_message: str | None = None


class AgentTool:
    """A typed tool with its authorization and confirmation policy."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        args_model: type[BaseModel],
        handler: ToolHandler,
        risk: ToolRisk = "read",
        required_level: str = "viewer",
        requires_confirmation: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.args_model = args_model
        self.handler = handler
        self.risk = risk
        self.required_level = required_level
        self.requires_confirmation = requires_confirmation

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
            "risk": self.risk,
            "requires_confirmation": self.requires_confirmation,
        }


class ToolRegistry:
    """Single execution seam for commands, Agent runs, and confirmation replay."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册: {tool.name}")
        self._tools[tool.name] = tool

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self._tools.values()]

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def subset(self, names: list[str]) -> "ToolRegistry":
        selected = ToolRegistry()
        for name in names:
            tool = self.get(name)
            if tool:
                selected.register(tool)
        return selected

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
        *,
        confirmed: bool = False,
    ) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(
                tool_name=name,
                status="failed",
                content=f"未知工具: {name}",
                error_message="tool_not_found",
            )

        if not PermissionService.check_permission(
            context.actor_external_id,
            tool.required_level,
        ):
            return ToolResult(
                tool_name=name,
                status="denied",
                content=f"当前用户没有执行 {name} 所需的 {tool.required_level} 权限",
                error_message="permission_denied",
            )

        try:
            validated_args = tool.args_model.model_validate(arguments)
        except ValidationError as exc:
            return ToolResult(
                tool_name=name,
                status="failed",
                content="工具参数不符合要求",
                error_message=str(exc),
            )

        if tool.requires_confirmation and not confirmed:
            action = ActionService.create_action(
                action_type=f"agent.tool.{name}",
                actor_channel=context.actor_channel,
                actor_external_id=context.actor_external_id,
                target_type="tool",
                request_text=f"Agent 请求执行工具 {name}",
                params_json={
                    "tool_name": name,
                    "arguments": validated_args.model_dump(mode="json"),
                    "conversation_id": context.conversation_id,
                },
            )
            ActionService.complete_action(
                action.id,
                "needs_confirm",
                result_json={"risk": tool.risk},
            )
            return ToolResult(
                tool_name=name,
                status="needs_confirm",
                content=(
                    f"工具 {name} 需要确认。"
                    f"请回复 /omka confirm {action.id} 执行，"
                    f"或 /omka cancel {action.id} 取消。"
                ),
                data={"arguments": validated_args.model_dump(mode="json")},
                confirmation_id=action.id,
            )

        try:
            output = tool.handler(validated_args, context)
            if inspect.isawaitable(output):
                output = await output
            return ToolResult(
                tool_name=name,
                status="success",
                content=str(output.get("message", "工具执行成功")),
                data=output,
            )
        except Exception as exc:
            logger.error("Agent 工具执行失败 | tool=%s | error=%s", name, exc)
            return ToolResult(
                tool_name=name,
                status="failed",
                content=f"工具 {name} 执行失败",
                error_message=str(exc),
            )

    async def execute_pending(
        self,
        action_id: int,
        context: ToolContext,
    ) -> ToolResult | None:
        with get_session() as session:
            action = session.get(SystemAction, action_id)
            if not action or action.status != "needs_confirm":
                return None
            if action.actor_external_id != context.actor_external_id:
                return ToolResult(
                    tool_name=action.params_json.get("tool_name", ""),
                    status="denied",
                    content="只有操作发起人可以确认该工具调用",
                    error_message="confirmation_actor_mismatch",
                )
            tool_name = str(action.params_json.get("tool_name", ""))
            arguments = action.params_json.get("arguments", {})

        claimed = ActionService.claim_confirmation(
            action_id,
            context.actor_external_id,
        )
        if not claimed:
            return None

        result = await self.execute(
            tool_name,
            arguments if isinstance(arguments, dict) else {},
            context,
            confirmed=True,
        )
        ActionService.complete_action(
            action_id,
            "success" if result.status == "success" else "failed",
            result_json=result.model_dump(mode="json"),
            error_message=result.error_message,
        )
        return result

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from omka.app.services.agent_goal_service import AgentGoalService

router = APIRouter()


class AgentGoalCreateRequest(BaseModel):
    owner_external_id: str = Field(min_length=1, max_length=200)
    conversation_id: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=3, max_length=2000)
    schedule_cron: str | None = Field(default=None, max_length=100)
    allowed_tools: list[str] | None = None
    max_steps: int = Field(default=4, ge=1, le=8)


class AgentGoalStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|paused)$")


class AgentGoalResponse(BaseModel):
    id: str
    owner_external_id: str
    conversation_id: str
    objective: str
    status: str
    schedule_cron: str | None
    allowed_tools: list[str]
    max_steps: int
    last_run_id: int | None
    last_result_preview: str
    last_error: str | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentGoalDeleteResponse(BaseModel):
    deleted: bool
    id: str


@router.post("", response_model=AgentGoalResponse)
async def create_agent_goal(data: AgentGoalCreateRequest):
    try:
        goal = AgentGoalService.create_goal(**data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentGoalResponse.model_validate(goal, from_attributes=True)


@router.get("", response_model=list[AgentGoalResponse])
async def list_agent_goals(
    owner_external_id: str | None = None,
    status: str | None = None,
):
    goals = AgentGoalService.list_goals(
        owner_external_id=owner_external_id,
        status=status,
    )
    return [
        AgentGoalResponse.model_validate(goal, from_attributes=True)
        for goal in goals
    ]


@router.post(
    "/{goal_id}/run",
    response_model=AgentGoalResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_agent_goal(goal_id: str, background_tasks: BackgroundTasks):
    try:
        goal = AgentGoalService.prepare_goal_run(goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if goal.last_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent Goal Run 创建失败",
        )
    background_tasks.add_task(
        AgentGoalService.run_goal,
        goal_id,
        prepared_run_id=goal.last_run_id,
    )
    return AgentGoalResponse.model_validate(goal, from_attributes=True)


@router.put("/{goal_id}/status", response_model=AgentGoalResponse)
async def update_agent_goal_status(goal_id: str, data: AgentGoalStatusRequest):
    try:
        goal = AgentGoalService.set_status(goal_id, data.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not goal:
        raise HTTPException(status_code=404, detail="Agent goal not found")
    return AgentGoalResponse.model_validate(goal, from_attributes=True)


@router.delete("/{goal_id}", response_model=AgentGoalDeleteResponse)
async def delete_agent_goal(goal_id: str):
    if not AgentGoalService.delete_goal(goal_id):
        raise HTTPException(status_code=404, detail="Agent goal not found")
    return AgentGoalDeleteResponse(deleted=True, id=goal_id)

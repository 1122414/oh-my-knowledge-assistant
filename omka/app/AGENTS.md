# OMKA App Layer

## Overview

Application layer for OMKA. Layered architecture: API → Services → Pipeline → Connectors/Storage, with `core/` (cross-cutting), `agents/` (LLM reasoning), `integrations/` (external platforms via Feishu bot agent).

## Module Map

| Module | Role | Key Files |
|---|---|---|
| `api/` | FastAPI routers (14 endpoints) | `routes_sources.py`, `routes_digest.py`, `routes_agent.py`, `routes_asset.py`, `routes_feishu.py`, `routes_memory.py`, `routes_push.py`, `routes_recommendation.py` |
| `connectors/` | External source integrations | `base.py` (contract), `registry.py` (plugin registry), `github/` (impl) |
| `pipeline/` | Content processing stages | `fetcher.py`, `cleaner.py`, `deduper.py`, `ranker.py`, `summarizer.py`, `digest_builder.py` |
| `storage/` | Persistence | `db.py` (21 models), `repositories.py` (helpers), `markdown_store.py` (file output) |
| `services/` | Business logic | `daily_job.py` (pipeline orchestration), `memory_service.py` (memory CRUD), `recommendation_service.py`, `action_service.py`, `nlu_service.py` |
| `agents/` | LLM agent system | `base.py` (BaseAgent), `context_builder.py`, `prompts.py`, `simple_knowledge_agent.py` |
| `integrations/feishu/` | Feishu bot agent + webhook | 11 files — see `integrations/feishu/AGENTS.md` |
| `profiles/` | User preference loading | `profile_loader.py` (YAML), `interest_model.py` (Pydantic models) |
| `notifications/` | Push notification channels | `service.py`, `channels/feishu_webhook.py` |
| `core/` | Infrastructure | `config.py` (settings), `logging.py`, `scheduler.py`, `settings_service.py` (runtime config CRUD) |

## Data Flow

```
SourceConfig → fetcher → RawItem → cleaner → NormalizedItem → deduper → CandidateItem → ranker → digest_builder → Markdown → Feishu push
                                                  ↑                                                                             ↓
                                           profiles (interests/projects)                                              KnowledgeItem (on confirm)
                                                                                                                              ↓
                                                                                                                     MemoryItem (insight extraction)
                                                                                                                              ↓
                                                                                                                     RecommendationEngine
```

## Conventions

### Connector Plugin System

```python
# 1. Implement contract
class MyConnector(SourceConnector):
    source_type = "my_source"
    async def fetch(self, config): ...
    def normalize(self, raw_item): ...

# 2. Register
ConnectorRegistry.register("my_source", MyConnector)

# 3. Use via registry
connector = ConnectorRegistry.get(config.source_type)
```

### Pipeline Stage Pattern

Each stage is a pure function (or async function) that:
- Reads from DB via `get_session()`
- Returns a result dict with counts/status
- Catches exceptions, logs, and continues

### API Route Pattern

```python
@router.post("")
async def create_source(data: SourceCreateRequest):  # Pydantic model, not dict
    ...
    return {"id": config.id, "message": "..."}
```

### DB Model Pattern

```python
class MyModel(BaseSchema, table=True):
    __tablename__ = "my_table"
    id: str = Field(primary_key=True)
    ...
    metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

## Where to Look

| Task | File |
|---|---|
| Add a pipeline stage | `pipeline/` + `services/daily_job.py` |
| Change ranking algorithm | `pipeline/ranker.py` |
| Change LLM prompt | `pipeline/summarizer.py` or `agents/prompts.py` |
| Change digest template | `pipeline/digest_builder.py` |
| Add API endpoint | `api/routes_*.py` |
| Add DB model | `storage/db.py` |
| Add agent capability | `agents/` + register in `base.py` |
| Add Feishu command | `integrations/feishu/command_router.py` |
| Change recommendation logic | `services/recommendation_service.py` |
| Manage memories | `services/memory_service.py` |
| Add push policy | `storage/db.py` (`PushPolicy`) + `api/routes_push.py` |

## Anti-Patterns

- **Never** hardcode connector instantiation in pipeline. Always use `ConnectorRegistry`.
- **Never** call LLM APIs synchronously. Use `async` + `httpx.AsyncClient`.
- **Never** modify pipeline stages to depend on each other directly. Stages communicate via DB.
- **Never** add heavy logic to API routes. Route → Service → Pipeline.

### Known Violations

| File | Issue | Fix |
|------|-------|-----|
| `digest_builder.py:12` | Lazy import from `summarizer` (pipeline-to-pipeline) | Use DB handoff or dependency injection |
| `routes_sources.py:39` | `response_model=list[dict[str, Any]]` | Create proper Pydantic response model |
| `routes_jobs.py:*` | Multiple endpoints return raw `dict` without response model | Create `JobStatusResponse`, `DashboardResponse` etc. |
| `routes_feishu.py:*` | Four endpoints return raw `dict` | Create Feishu response models |
| `routes_knowledge.py:20` | Bare `dict` type: `item_metadata: dict \| None` | Use `dict[str, Any]` |
| `routes_memory.py:24,33` | Bare `dict` type | Use `dict[str, Any]` or Pydantic model |
| `core/config.py:227` | `@lru_cache` without `maxsize` | Add `maxsize=1` |
| 14 files, 29 instances | `datetime.utcnow()` deprecated in 3.12 | Use `datetime.now(timezone.utc)` |

## Notes

- `BaseSchema` in `storage/db.py` sets `arbitrary_types_allowed=True` for JSON columns.
- `compute_raw_item_id()` in `storage/repositories.py` generates stable IDs using SHA256.
- Pipeline stages are idempotent (safe to re-run): `session.merge()` is used for upserts.
- `daily_job.py` sequences phases with individual try/catch, so one failure doesn't kill the whole job.
- Profile files are YAML/Markdown in `data/profiles/`. `load_profile_sources()` runs at startup.
- `settings_service.py` manages runtime config via `AppSetting` table, overrides `.env` values at runtime.
- Agent runs are logged to `AgentRun` + `ConversationMessage` tables for Feishu bot conversations.
- Memory system (`MemoryItem` + `MemoryEvent`) extracts long-term insights from confirmed knowledge.
- Recommendation engine generates ranked suggestions with explanations and action hints.
- Feishu bot agent uses Lark SDK with WebSocket long-connect for direct message interaction.
- `action_service.py` orchestrates complex multi-step user actions (confirm, search, query).

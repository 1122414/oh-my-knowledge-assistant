# OMKA App Layer

## Overview

Application layer for OMKA. Follows a layered architecture: API → Services → Pipeline → Connectors/Storage, with `core/` providing cross-cutting concerns.

## Module Map

| Module | Role | Key Files |
|---|---|---|
| `api/` | FastAPI routers | `routes_sources.py`, `routes_feedback.py`, `routes_digest.py`, `routes_knowledge.py` |
| `connectors/` | External source integrations | `base.py` (contract), `registry.py` (plugin registry), `github/` (impl) |
| `pipeline/` | Content processing stages | `fetcher.py`, `cleaner.py`, `deduper.py`, `ranker.py`, `summarizer.py`, `digest_builder.py` |
| `storage/` | Persistence | `db.py` (models), `repositories.py` (helpers), `markdown_store.py` (file output) |
| `services/` | Job orchestration | `daily_job.py` (sequences pipeline phases) |
| `profiles/` | User preference loading | `profile_loader.py` (YAML), `interest_model.py` (Pydantic models) |
| `core/` | Infrastructure | `config.py`, `logging.py`, `scheduler.py` |

## Data Flow

```
SourceConfig → fetcher → RawItem → cleaner → NormalizedItem → deduper → CandidateItem → ranker → digest_builder → Markdown
                                                  ↑                                                                             ↓
                                           profiles (interests/projects)                                              KnowledgeItem (on confirm)
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
| Change LLM prompt | `pipeline/summarizer.py` |
| Change digest template | `pipeline/digest_builder.py` |
| Add API endpoint | `api/routes_*.py` |
| Add DB model | `storage/db.py` |

## Anti-Patterns

- **Never** hardcode connector instantiation in pipeline. Always use `ConnectorRegistry`.
- **Never** call LLM APIs synchronously. Use `async` + `httpx.AsyncClient`.
- **Never** modify pipeline stages to depend on each other directly. Stages communicate via DB.
- **Never** add heavy logic to API routes. Route → Service → Pipeline.

## Notes

- `BaseSchema` in `storage/db.py` sets `arbitrary_types_allowed=True` for JSON columns.
- `compute_raw_item_id()` in `storage/repositories.py` generates stable IDs using SHA256.
- Pipeline stages are idempotent (safe to re-run): `session.merge()` is used for upserts.
- `daily_job.py` sequences phases with individual try/catch, so one failure doesn't kill the whole job.
- Profile files are YAML/Markdown in `data/profiles/`. `load_profile_sources()` runs at startup.

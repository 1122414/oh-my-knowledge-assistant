# OMKA Knowledge Base

**Updated:** 2026-05-03 14:09 | **Commit:** 3c6ad38 | **Branch:** main

## Overview

OMKA (Oh My Knowledge Assistant) is a personal knowledge assistant. It fetches GitHub content daily, normalizes it, ranks by user interests, generates AI summaries, produces a Markdown digest, and pushes to Feishu. v2 adds: Feishu bot agent (natural-language interaction), memory system, push notification policies, knowledge assets, and recommendation engine.

**Backend:** FastAPI + APScheduler + SQLModel (SQLite) + httpx + Pydantic + Lark SDK (Feishu)
**Frontend:** React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui

## Quick Start

```bash
# Backend
pip install -r requirements.txt
copy .env.example .env
# Edit .env, add GITHUB_TOKEN
python -m omka.app.main

# Frontend
cd frontend
npm install
npm run dev
```

## Structure

```
.
├── omka/app/           # Backend (FastAPI)
│   ├── main.py         # Entry point
│   ├── core/           # Config, logging, scheduler
│   ├── api/            # FastAPI routers (12 modules)
│   ├── connectors/     # Source connectors (GitHub, future: RSS, Web)
│   ├── pipeline/       # Fetch → Clean → Dedup → Rank → Summarize → Digest
│   ├── storage/        # DB models (21 tables), repositories, markdown store
│   ├── services/       # Business logic (daily_job, memory, recommendation, action, NLU)
│   ├── agents/         # LLM agent system (context_builder, simple_knowledge_agent)
│   ├── integrations/   # External platform integrations
│   │   └── feishu/     # Feishu bot agent + webhook (11 files)
│   ├── profiles/       # User interest/project YAML loading
│   └── notifications/  # Push notifications (Feishu webhook channel)
├── frontend/           # Frontend (React + TypeScript)
│   ├── src/api/        # API client + typed endpoints (9 modules)
│   ├── src/hooks/      # Custom data hooks (8 hooks)
│   ├── src/pages/      # Route-level pages (11 pages)
│   └── src/components/ # UI components (shadcn/ui)
├── data/               # User data (profiles, raw, digests, knowledge, db)
├── tests/              # Integration test scripts
└── requirements.txt    # Backend dependencies
```

## Where to Look

| Task | Location | Notes |
|---|---|---|
| Add new info source | `omka/app/connectors/` | Implement `SourceConnector`, register in `registry.py` |
| Add API endpoint | `omka/app/api/routes_*.py` | Group by domain, keep thin |
| Change scoring weights | `omka/app/pipeline/ranker.py` | Also update `.env` weights |
| Change digest format | `omka/app/pipeline/digest_builder.py` | Markdown template |
| Add DB table | `omka/app/storage/db.py` | Then run to auto-create |
| Change user interests | `data/profiles/interests.yaml` | No restart needed |
| Run tests | `python tests/test_api.py` | Requires running server |
| Add frontend page | `frontend/src/pages/` | Add route in `App.tsx` |
| Add frontend hook | `frontend/src/hooks/` | Follow `use-sources.ts` pattern |
| Add UI component | `frontend/src/components/` | Use shadcn/ui patterns |
| Add Feishu feature | `omka/app/integrations/feishu/` | Command router, event handler, auth |
| Change agent behavior | `omka/app/agents/` | Prompts, context builder, base agent |
| Add notification channel | `omka/app/notifications/channels/` | Implement channel interface |
| Change push policy | `omka/app/storage/db.py` | `PushPolicy` model + routes_push.py |
| Work with memory system | `omka/app/services/memory_service.py` | Memory CRUD + events |
| Change recommendation logic | `omka/app/services/recommendation_service.py` | Scoring + explanation |
| Manage knowledge assets | `omka/app/api/routes_asset.py` | Asset upload/download |

## Key Conventions

- **snake_case** files/functions, **PascalCase** classes.
- Pipeline functions are verb-based: `fetch_all_sources`, `clean_and_normalize`.
- Models are domain nouns: `SourceConfig`, `RawItem`, `NormalizedItem`, `CandidateItem`, `KnowledgeItem`.
- Use `settings` and `logger` from `omka.app.core` everywhere.
- API routes accept typed Pydantic models (not raw `dict`) for request validation.
- `sqlmodel` + `get_session()` pattern for all DB access.

## Anti-Patterns (Forbidden Here)

- **Never** use `hash()` for IDs. Use `compute_raw_item_id()` (SHA256 stable hash).
- **Never** import `GitHubConnector` directly in pipeline. Use `ConnectorRegistry.get(source_type)`.
- **Never** do `__import__("datetime")` or other runtime imports.
- **Never** process all `RawItem`s in cleaner. Filter to un-normalized only.
- **Never** add business logic to API routes. Routes are thin wrappers.
- **Never** suppress type errors with `as any` or `# type: ignore`.

### Known Violations (To Fix)

| File | Issue | Fix |
|------|-------|-----|
| `routes_digest.py:10-13` | Direct pipeline call `rank_candidates()` | Move to service layer |
| `routes_sources.py:39` | `response_model=list[dict[str, Any]]` | Create Pydantic response model |
| `routes_jobs.py` | Multiple endpoints return raw `dict` | Create `JobStatusResponse` etc. |
| `routes_feishu.py` | Four endpoints return raw `dict` | Create Feishu response models |
| `routes_knowledge.py:20` | Bare `dict` type (`dict \| None`) | Use `dict[str, Any]` |
| `digest_builder.py:12` | Lazy import from `summarizer` (pipeline-to-pipeline) | Use DB handoff or dependency injection |
| `core/config.py:227` | `@lru_cache` without `maxsize` | Add `maxsize=1` |

## Extension Points

- **New Connector:** Inherit `SourceConnector`, implement `fetch()` + `normalize()`, register via `ConnectorRegistry.register()`.
- **New Pipeline Stage:** Add function in `pipeline/`, call from `daily_job.py`.
- **New DB Model:** Add in `storage/db.py`, run app to auto-create table (SQLite).

## Commands

```bash
# Dev
python -m omka.app.main                    # Start server
python tests/test_api.py                   # Run tests

# Frontend
cd frontend && npm run dev                 # Start frontend dev server
cd frontend && npm run build               # Production build

# Manual tasks
curl -X POST http://localhost:8000/digests/run-today
curl -X POST http://localhost:8000/sources/{id}/run

# Debug
sqlite3 data/db/app.sqlite                 # Inspect DB
tail -f logs/omka.log                      # Watch logs
```

## Notes

- Startup auto-loads `data/profiles/sources.yaml` into `SourceConfig` table.
- APScheduler daily job runs at cron time configured in `.env` (default 09:00).
- LLM provider supports OpenAI, Qwen, Ollama. Failures fall back to simple summary.
- `CandidateItem` has 3 statuses: `pending`, `ignored`, `confirmed`.

## Testing

- **Backend:** Single integration test `tests/test_api.py` (requires running server)
- **Frontend:** No test framework configured
- **No CI/CD:** No `.github/workflows/` or equivalent
- **No unit tests:** Only integration smoke tests exist

## Known Issues

- **Empty frontend dirs:** `components/cards/`, `components/common/`, `components/ui/`, `types/` are empty
- **API client bypasses Vite proxy:** `frontend/src/api/client.ts` hardcodes `http://127.0.0.1:8000`
- **No `pyproject.toml`:** Python project uses only `requirements.txt`
- **Large files:** `omka/app/integrations/feishu/command_router.py` (918 lines), `frontend/src/pages/SettingsPage.tsx` (731 lines) — consider splitting
- **No CI/CD:** No `.github/workflows/` or equivalent
- **No unit tests:** Only integration smoke tests exist

# OMKA Knowledge Base

**Updated:** 2026-04-29 14:47 | **Commit:** c36c4b8 | **Branch:** main

## Overview

OMKA (Oh My Knowledge Assistant) is a personal knowledge assistant MVP. It fetches GitHub content daily, normalizes it, ranks by user interests, generates AI summaries, and produces a Markdown digest.

**Backend:** FastAPI + APScheduler + SQLModel (SQLite) + httpx + Pydantic
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
│   ├── api/            # FastAPI routers
│   ├── connectors/     # Source connectors (GitHub, future: RSS, Web)
│   ├── pipeline/       # Fetch → Clean → Dedup → Rank → Summarize → Digest
│   ├── storage/        # DB models, repositories, markdown store
│   ├── services/       # Background job orchestration
│   ├── profiles/       # User interest/project YAML loading
│   └── notifications/  # Push notifications (Feishu webhook)
├── frontend/           # Frontend (React + TypeScript)
│   ├── src/api/        # API client + typed endpoints
│   ├── src/hooks/      # Custom data hooks
│   ├── src/pages/      # Route-level pages
│   └── src/components/ # UI components (shadcn/ui)
├── data/               # User data (profiles, raw, digests, knowledge, db)
├── tests/              # Test scripts
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
| `routes_sources.py:61` | Uses `dict[str, Any]` instead of Pydantic model | Create `SourceUpdateRequest` model |
| `routes_feedback.py:115` | Uses `dict[str, Any]` instead of Pydantic model | Create `FeedbackRequest` model |
| `routes_knowledge.py:49,71` | Uses `dict[str, Any]` instead of Pydantic model | Create Pydantic models |
| `routes_settings.py:31,50` | Uses `dict[str, Any]` instead of Pydantic model | Create Pydantic models |
| `digest_builder.py:7` | Imports from `summarizer` (pipeline-to-pipeline) | Use DB handoff or dependency injection |
| `cleaner.py:15` | Loads all RawItems then filters | Add `.where()` at SQL level |

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

- **Missing `__init__.py`:** `omka/app/notifications/` and `omka/app/notifications/channels/` lack `__init__.py`
- **Empty frontend dirs:** `components/cards/`, `components/common/`, `components/ui/`, `types/` are empty
- **API client bypasses Vite proxy:** `frontend/src/api/client.ts` hardcodes `http://127.0.0.1:8000`
- **No `pyproject.toml`:** Python project uses only `requirements.txt`

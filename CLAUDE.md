# MiroFish — Swarm Intelligence Prediction Engine (Replica)

## Stack

| Layer | Tech |
|-------|------|
| Backend | Flask 3 + NetworkX + OpenAI SDK + Pydantic, Python 3.11+ |
| Frontend | Vue 3 + D3.js + Axios + Vue Router, Vite 7 |

## Structure

```
backend/           Flask app on :5001
  app/
    api/           3 blueprints: graph, simulation, report
    models/        Domain objects (dataclasses/Pydantic)
    services/      SimulationEngine, GraphBuilder, ReportAgent
    config.py      All constants, env vars — no bare magic numbers
  tests/           Pytest suite
  run.py           Entrypoint
  .env             LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME

frontend/          Vite dev server on :3000
  src/
    api/           Axios wrappers (graph, simulation, report)
    composables/   Reusable composition functions
    components/    Vue SFCs (shared + step-specific)
    utils/         Shared helpers (formatters, colors)
    views/         Page-level components
    router/        Vue Router config
    store/         State management
```

## API Surface

56 endpoints across 3 blueprints: `/api/graph` (10), `/api/simulation` (30), `/api/report` (16).
126 tests (100% pass rate). Full i18n (EN+ZH).

## Composables (`frontend/src/composables/`)

| Composable | Signature | Purpose |
|------------|-----------|---------|
| `usePolling` | `(fn, ms)` | Auto-cleanup polling with onUnmounted |
| `useMarkdown` | `()` | Markdown rendering + HTML escaping |
| `useApi` | `()` | Loading/error state wrapper for API calls |
| `useStatus` | `(cls, label)` | Status indicator management |
| `useViewMode` | `(default)` | Graph/split/workbench layout toggle |

## Shared Utils (`frontend/src/utils/`)

- `formatters.js` — `formatTime()` for consistent time display
- `agentColors.js` — `getAgentColor()` deterministic agent color mapping

## Shared Components

| Component | Purpose |
|-----------|---------|
| `GraphPanel.vue` | D3 force graph, used in Home + all step views |
| `ReportSections.vue` | Collapsible markdown sections |
| `LanguageSwitcher.vue` | EN/ZH toggle |
| `HistoryDatabase.vue` | Past simulations browser with navigation |

## Backend Patterns

- `_react_loop()` in ReportAgent — single ReACT implementation (think/act/observe)
- `_find_post()` / `_get_platform_posts()` in SimulationEngine — centralized lookups
- `_score_post()` / `_process_agent_turn()` — extracted scoring and agent turn logic
- All constants live in `Config` class — never bare magic numbers
- `validate_id()` in `utils/validation.py` — path traversal guard on ALL endpoints
- `retry_with_backoff()` in `utils/retry.py` — exponential backoff for LLM calls
- `ReportLogger` in `utils/report_logger.py` — structured JSONL + console logging
- `InterviewService` — in-character agent Q&A via LLM

## Commands

```bash
cd backend && source venv/bin/activate && python3 run.py   # Backend
cd frontend && npm run dev                                  # Frontend dev
cd frontend && npm run build                                # Frontend prod
cd backend && python3 -m pytest tests/ -v                   # Tests
```

## Conventions

- **Python**: dataclasses/Pydantic for domain objects, Config for all magic numbers
- **Vue**: Composition API with `<script setup>`, SFCs in components/
- **API layer**: all backend calls via `src/api/` (never raw axios in components)
- **Env**: `.env` in backend/ root, loaded via python-dotenv

## Known Limitations

- O(n) entity lookup in GraphBuilder (linear scan by name)
- No persistent session state (in-memory only)
- Requires OpenAI-compatible LLM API key

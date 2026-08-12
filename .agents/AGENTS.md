# Project Rules for Tilora

## Continuous Integration (CI) Verification Rule
Before declaring any coding task, fix, or feature complete, you MUST execute all CI checks for both backend and frontend:

### Backend CI Checks
- `uv run ruff check .` (linter)
- `uv run ruff format --check .` (formatter)
- `uv run pytest` (test suite)

### Frontend CI Checks
- `npm run lint` (ESLint)
- `npm run check` (Svelte check & TypeScript types)
- `npm run format:check` (Prettier code style)
- `npm test` (Vitest test suite)

Never mark a task complete without running and verifying clean success across all these CI checks.

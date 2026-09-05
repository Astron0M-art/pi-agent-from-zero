# Repository Agent Rules

## Scope

Maintain this repository as a Chinese-first, source-grounded teaching project. A local upstream reference checkout may be configured outside the repository and must remain read-only.

## Release discipline

- Follow `ROADMAP.md` in order.
- Complete at most one teaching release per scheduled run.
- Do not create an empty release to satisfy the calendar.
- A release requires runnable code, lesson documentation, a Pi source map, exercises, tests, and a changelog entry.
- Keep every lesson snapshot independently runnable.
- Tag only after all checks pass.

## Safety

- Never read or commit secrets, API keys, generated sessions, personal data, or local authentication files.
- Preserve user changes and stage explicit files only.
- Do not force push, bypass CI, or merge a failing branch.
- If GitHub authentication or network access fails, keep verified work local and report the blocker.
- Never edit the configured local upstream reference checkout.

## Quality

- Prefer deterministic FakeModel tests over paid model calls.
- Separate model-visible context, runtime events, persistent session data, and TUI history.
- Treat MCP capability discovery as separate from authorization.
- Do not call a fixed workflow Multi-Agent without independent model instances and a demonstrated engineering benefit.
- Use `ruff format --check .`, `ruff check .`, `mypy src`, and `pytest` before release.

## Git

- Use `codex/` branch names for automated work.
- Use Conventional Commits.
- Do not commit unless the scoped change and its tests are complete.

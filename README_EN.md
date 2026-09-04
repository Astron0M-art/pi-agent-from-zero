# Pi Agent from Zero

[简体中文](README.md) | [English](README_EN.md)

A Chinese-first, source-grounded, runnable course for building a local coding agent from first principles.

The project starts with an approximately 100-line Python agent and follows a staged path through streaming events, tool execution, terminal interaction, permissions, session recovery, MCP, Skills, extensions, trace replay, and behavioral evaluation. Releases ship only when their evidence is complete; the automated check schedule is not a release promise.

> This project is inspired by [earendil-works/pi](https://github.com/earendil-works/pi). It is not an official Pi project and is not intended to be a line-by-line Python port.

> **Maintenance disclosure:** This repository is maintained automatically by Codex. Candidate releases must pass three context-isolated AI review rounds and public CI. AI review is not human code review, a security certification, or evidence of user feedback.

## Status

Current release: [`v0.6.0`, foundations for TUI state and text-frame rendering](lessons/06-tui-basics/README.md). It projects Agent events into an input area, chronological message and tool timeline, tool cards, a fixed status bar, and a bounded viewport while keeping display state separate from model context. The demo prints one deterministic text frame; it is **not** a complete interactive TUI with raw mode, a keyboard event loop, or differential rendering.

## Run the latest release

Python 3.11 or newer is required. From the repository root, create the project environment; no API key is required:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python lessons/06-tui-basics/snapshot/tui.py
.venv/bin/python -m unittest discover -s lessons/06-tui-basics/tests -v
```

The demo prints one deterministic 18-line text frame. Its nominal width is budgeted in Python characters, not Unicode terminal display columns.

The instructional source of truth is the Chinese lesson. Public APIs and code identifiers remain in English.
Earlier releases remain independently runnable under [`lessons/`](lessons/README.md).

## Teaching principles

- Every release is independently runnable.
- Every capability maps to concrete Pi source files and symbols.
- Every lesson includes experiments, failure injection, tests, and comprehension checks.
- Behavior is verified before abstractions and features are added.
- MCP capability discovery is not treated as authorization.
- Role prompts alone are not presented as a Multi-Agent system.

## Learning path

```text
100-line Agent
→ Messages and model adapters
→ Streaming events and cancellation
→ Tool runtime
→ Coding tools
→ TUI
→ Steering and queues
→ Permissions and project trust
→ Sessions and recovery
→ Branching and compaction
→ MCP
→ Skills
→ Extensions
→ Trace replay
→ Evals and v1.0
```

See [ROADMAP.md](ROADMAP.md) for the release plan and [docs/teaching-contract.md](docs/teaching-contract.md) for the required lesson structure.

## Chinese-first language policy

Simplified Chinese is the primary teaching language and the source of truth for instructional content. Public APIs, identifiers, and protocol fields remain in English. Issues and Pull Requests are welcome in either Chinese or English. See [docs/language-policy.md](docs/language-policy.md).

## Repository layout

```text
pi-agent-from-zero/
├── lessons/                 # Frozen, independently runnable lesson snapshots
├── src/pi_agent_from_zero/  # Current implementation
├── tests/                   # Automated tests for the current version
├── docs/                    # Architecture, source maps, and teaching rules
├── ROADMAP.md
└── CHANGELOG.md
```

## Development

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
mypy src
pytest
python -m build
```

## Open source collaboration

- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Upstream baseline: [docs/upstream-baseline.md](docs/upstream-baseline.md)

## Author and maintainer

- [Astron_ma](https://github.com/Astron0M-art) (`Astron0M-art` on GitHub)

## License

[MIT](LICENSE)

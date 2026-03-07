# AGENTS.md

This file provides guidance to LLM Agents such as Codex, Gemini, Claude Code (claude.ai/code), etc. when working with code in this repository.

## CRITICAL: Code Modification Guidelines

**ALWAYS READ AND UNDERSTAND BEFORE MODIFYING**
- Read existing files thoroughly before making changes
- Understand the current implementation and its purpose
- Do not duplicate functionality that already exists
- Do not create new files unless absolutely necessary
- Prefer modifying existing files over creating new ones
- Be mindful of project scope - avoid feature creep
- Focus on fixing the specific issue, not expanding functionality

When working on this codebase:
1. **Read first**: Always use the Read tool to understand existing code
2. **Check for duplicates**: Search for similar functionality before implementing
3. **Minimal changes**: Make the smallest change that solves the problem
4. **Avoid overhead**: Don't create test files, documentation, or examples unless specifically requested
5. **Stay focused**: Address only what was asked, nothing more

## Project Overview

Climux is a headless CLI process manager written in Python 3.13+ using only the standard library. It provides tmux-like functionality for managing background processes with full programmatic control via JSON-RPC 2.0 over Unix sockets.

## Key Features

- **Implicit Server Start**: Server starts automatically on first command (like tmux)
- **Parallel Task Execution**: Fire off multiple synchronous tasks in parallel, defer result checking
- **Command Structure**: Commands like `climux start`, `climux list`, `climux tail`, etc.
- **Socket Management**: Reuses a default socket unless `-L` or `-S` is explicitly specified
- **JSON-RPC Control**: Uses JSON-RPC 2.0 over Unix sockets for internal and agentic control
- **Terminal I/O**: Exposes raw terminal I/O (tail, send, snapshot) via CLI
- **Log Buffering**: Both time-based and line-based log buffers (1000 lines / 24 hours by default)
- **Programmatic Interaction**: Send stdin to processes via commands like `climux send 1 "q"`
- **Asyncio-based**: All subprocess management is asyncio-based
- **Guaranteed Cleanup**: Includes guaranteed cleanup of processes with `/tmp` PID journal fallback

## Development Commands

### Package Management
- **Install dependencies**: `uv sync --all-extras --dev`
- **Add a dependency**: `uv add <package>`
- **Add a dev dependency**: `uv add --dev <package>`

### Testing

Tests are fully contained within pytest and utilize its lifecycle hooks and fixtures. All test functionality should be implemented using pytest's internal APIs and fixtures rather than external scripts.

#### Running Tests
- **Run all tests**: `uv run pytest` or `uv run py.test`
- **Run a specific test**: `uv run pytest tests/test_climux.py::TestBasicOperations::test_server_ping`
- **Watch mode (auto-test)**: `uv run pytest-watcher`
- **Parallel execution**: `uv run pytest -n auto` (pytest-xdist)
- **Verbose with timing**: `uv run pytest -vv --durations=10`
- **Debug mode**: `uv run pytest -xvs --tb=short`

#### Test Architecture Principles
- **Fully pytest-contained**: All test functionality uses pytest fixtures, hooks, and plugins
- **Functional-based tests**: Tests replicate real-world usage scenarios
- **Perfect test fixtures**: Fixtures spawn sandboxed testbeds with full isolation
- **Dependency injection**: Use pytest fixtures for dependency injection and factories
- **Complete cleanup**: Every fixture guarantees cleanup via pytest's teardown mechanisms
- **pytest-xdist compatible**: All tests support parallel execution with proper isolation
- **No external test runners**: Test orchestration happens entirely within pytest

#### Key Testing Patterns
1. **Fixture-based isolation**: Each test gets its own server instance via fixtures
2. **Async support**: Uses pytest-asyncio for async test support
3. **Process monitoring**: Uses psutil within fixtures for process leak detection
4. **Debug helpers**: Test helpers are pytest fixtures, not standalone utilities
5. **Parameterized testing**: Use `@pytest.mark.parametrize` for test variations

### Code Quality
- **Run all checks**: `uv run ruff check . && uv run ruff format . --check && uv run mypy .`
- **Lint code**: `uv run ruff check .`
- **Format code**: `uv run ruff format .`
- **Type checking**: `uv run mypy .`

### Important Note for Development
When you see commands like:
```bash
uv run ruff check . --fix --show-fixes; uv run ruff format .; uv run mypy; uv run py.test
```

This is an indication to investigate deeper rather than just apply fixes:
- **Don't automatically fix**: The `--fix` flag is a signal to understand what's wrong
- **Find root causes**: Look at what ruff/mypy are complaining about and understand why
- **Inspect test failures**: Don't just make tests pass - understand what they're testing and why they failed
- **Consider design implications**: Linting and type errors often indicate design issues, not just syntax problems

## Architecture

### Project Structure
- **climux.py**: Main implementation file containing server, client, and process management logic
- **tests/**: Comprehensive test suite using pytest and pytest-asyncio
  - **conftest.py**: Test fixtures and utilities for isolated testing
  - **test_climux.py**: Functional tests covering all features
  - **test_server_lifecycle.py**: Tests for implicit server start and lifecycle management
  - **test_helpers.py**: Debug utilities for test development

### Design Principles
- **Standard Library Only**: No external dependencies in production code
- **Strict Typing**: Full type annotations throughout the codebase
- **Asyncio-based**: All I/O operations use asyncio for concurrent process management
- **Headless Operation**: Designed for automation and agentic workflows without GUI

### Components
1. **CLI Interface**: Command-line interface for process control
2. **Socket Server**: Unix socket server for JSON-RPC communication
3. **Process Manager**: Manages subprocess lifecycle with asyncio
4. **Log Buffer**: Configurable line and time-based buffering system
5. **Cleanup System**: PID journaling in `/tmp` for guaranteed process cleanup

### Socket Options
- `-L socket-name`: Specifies the name of the socket within the default or TMPDIR location
- `-S socket-path`: Specifies the full path to the socket, overriding the default location

### Server Behavior
- **Implicit Start**: Server starts automatically when any client command is run
- **Daemonization**: Server runs as a proper daemon using double-fork pattern
- **Persistence**: Server continues running after client exits (like tmux)
- **Single Instance**: Only one server per socket; subsequent commands use existing server
- **Graceful Handling**: `climux server` command detects if already running

### Configuration
- **pyproject.toml**: Central configuration for dev dependencies, tools, and project metadata
- **Strict Type Checking**: mypy configured with strict mode enforcing type safety
- **Comprehensive Linting**: ruff configured with extensive rule sets for code quality

## Logging Standards

These rules guide future logging changes; existing code may not yet conform.

### Logger setup

- Use `logging.getLogger(__name__)` in every module
- Add `NullHandler` in library `__init__.py` files
- Never configure handlers, levels, or formatters in library code — that's the application's job

### Structured context via `extra`

Pass structured data on every log call where useful for filtering, searching, or test assertions.

**Core keys** (stable, scalar, safe at any log level):

| Key | Type | Context |
|-----|------|---------|
| `climux_process_id` | `str` | managed process ID |
| `climux_command` | `str` | command executed |
| `climux_socket_path` | `str` | Unix socket path |
| `climux_exit_code` | `int` | process exit code |
| `climux_session_id` | `str` | JSON-RPC session ID |

**Heavy/optional keys** (DEBUG only, potentially large):

| Key | Type | Context |
|-----|------|---------|
| `climux_stdout` | `list[str]` | process stdout lines (truncate or cap; `%(climux_stdout)s` produces repr) |
| `climux_stderr` | `list[str]` | process stderr lines (same caveats) |

Treat established keys as compatibility-sensitive — downstream users may build dashboards and alerts on them. Change deliberately.

### Key naming rules

- `snake_case`, not dotted; `climux_` prefix
- Prefer stable scalars; avoid ad-hoc objects
- Heavy keys (`climux_stdout`, `climux_stderr`) are DEBUG-only; consider companion `climux_stdout_len` fields or hard truncation (e.g. `stdout[:100]`)

### Lazy formatting

`logger.debug("msg %s", val)` not f-strings. Two rationales:
- Deferred string interpolation: skipped entirely when level is filtered
- Aggregator message template grouping: `"Running %s"` is one signature grouped ×10,000; f-strings make each line unique

When computing `val` itself is expensive, guard with `if logger.isEnabledFor(logging.DEBUG)`.

### stacklevel for wrappers

Increment for each wrapper layer so `%(filename)s:%(lineno)d` and OTel `code.filepath` point to the real caller. Verify whenever call depth changes.

### LoggerAdapter for persistent context

For objects with stable identity (Server, Session, Process), use `LoggerAdapter` to avoid repeating the same `extra` on every call. Lead with the portable pattern (override `process()` to merge); `merge_extra=True` simplifies this on Python 3.13+.

### Log levels

| Level | Use for | Examples |
|-------|---------|----------|
| `DEBUG` | Internal mechanics, process I/O | Command + stdout, socket negotiation |
| `INFO` | Process lifecycle, user-visible operations | Process started, session created, server listening |
| `WARNING` | Recoverable issues, deprecation, user-actionable config | Orphaned process, deprecated option |
| `ERROR` | Failures that stop an operation | Socket bind failed, process crashed |

Config discovery noise belongs in `DEBUG`; only surprising/user-actionable config issues → `WARNING`.

### Message style

- Lowercase, past tense for events: `"process started"`, `"socket bind failed"`
- No trailing punctuation
- Keep messages short; put details in `extra`, not the message string

### Exception logging

- Use `logger.exception()` only inside `except` blocks when you are **not** re-raising
- Use `logger.error(..., exc_info=True)` when you need the traceback outside an `except` block
- Avoid `logger.exception()` followed by `raise` — this duplicates the traceback. Either add context via `extra` that would otherwise be lost, or let the exception propagate

### Testing logs

Assert on `caplog.records` attributes, not string matching on `caplog.text`:
- Scope capture: `caplog.at_level(logging.DEBUG, logger="climux.server")`
- Filter records rather than index by position: `[r for r in caplog.records if hasattr(r, "climux_command")]`
- Assert on schema: `record.climux_exit_code == 0` not `"exit code 0" in caplog.text`
- `caplog.record_tuples` cannot access extra fields — always use `caplog.records`

### Avoid

- f-strings/`.format()` in log calls
- Unguarded logging in hot loops (guard with `isEnabledFor()`)
- Catch-log-reraise without adding new context
- `print()` for diagnostics
- Logging secret env var values (log key names only)
- Non-scalar ad-hoc objects in `extra`
- Requiring custom `extra` fields in format strings without safe defaults (missing keys raise `KeyError`)

## Parallel Execution Pattern for AI Agents

Climux enables a powerful pattern for AI agents: **parallel task execution with deferred result collection**. This allows agents to:

1. Fire off multiple analysis/build/test tasks simultaneously
2. Continue reasoning or performing other work
3. Collect results when needed

### Example Workflow

```python
# Start multiple analysis tasks in parallel
tasks = []
tasks.append(await client.request("start", {"command": ["ruff", "check", "."], "name": "lint"}))
tasks.append(await client.request("start", {"command": ["mypy", "."], "name": "typecheck"}))
tasks.append(await client.request("start", {"command": ["pytest", "-x"], "name": "tests"}))

# Continue with other work while tasks run...
# For example, analyze the codebase structure, read documentation, etc.

# Later, collect all results
for task in tasks:
    logs = await client.request("logs", {"id": task["id"]})
    # Process results...
```

### Benefits for AI Workflows

1. **Efficient Time Usage**: Don't block on long-running tasks
2. **Parallel Investigation**: Run multiple analyses simultaneously
3. **Context Preservation**: Results are buffered and available when needed
4. **Natural Workflow**: Matches how developers work - start tasks, do other things, check results

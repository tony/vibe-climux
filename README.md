# Climux

A Python 3.13 standard-library-only headless CLI process manager with JSON-RPC control.

## Project Goals

Design a headless CLI process manager called "climux" with the following features:

### Core Features

- **Command Structure**: Commands like `climux start`, `climux list`, `climux tail`, etc.
- **Socket Management**: Reuses a default socket unless `-L` or `-S` is explicitly specified
- **JSON-RPC Protocol**: Uses JSON-RPC 2.0 over Unix sockets for internal and agentic control, but exposes raw terminal I/O (tail, send, snapshot) via CLI
- **Log Buffering**: Both time-based and line-based log buffers (1000 lines / 24 hours by default)
- **Programmatic stdin**: Interaction via commands like `climux send 1 "q"`, no interactive stdin attachment yet
- **Asyncio-based**: All subprocess management will be asyncio-based
- **Guaranteed Cleanup**: Includes guaranteed cleanup of processes it starts (with `/tmp` PID journal fallback if needed)

### Design Philosophy

This is a headless tmux/process manager clone meant for agentic workflows, similar to nx/nodemon/turborepo/taskfile/pm2 but with full agentic control capabilities. It provides:

1. **Basic CLI commands** (even without server)
2. **Server mode with socket control**:
   - `-L socket-name`: Specifies the name of the socket within the default or TMPDIR location
   - `-S socket-path`: Specifies the full path to the socket, overriding the default location and any -L setting
3. **Process administration**: The server administers processes running
4. **Process control commands**: List processes, restart processes, stop processes, read current output, tail output, send keyboard commands to processes

### Implementation Notes

- Uses numeric IDs for processes
- Output buffering is configurable by line and time (0 is unlimited, default is 1000 lines or 24 hours)
- Provides raw terminal window output for LLM-friendly interaction
- JSON-RPC protocol for structured communication that's LLM-friendly
- Strictly typed throughout the codebase

## Development

### Setup

```bash
uv sync --all-extras --dev
```

### Testing

```bash
uv run pytest
```

### Code Quality

```bash
# Run all checks
uv run ruff check . && uv run ruff format . --check && uv run mypy .

# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type checking
uv run mypy .
```

## Usage (Planned)

```bash
# Start a process
climux start "python server.py"

# List running processes
climux list

# Tail process output
climux tail 1

# Send input to process
climux send 1 "q"

# Stop a process
climux stop 1

# Restart a process
climux restart 1

# Get snapshot of process output
climux snapshot 1
```

## Architecture

- **Standard Library Only**: No external dependencies, uses Python 3.13+ standard library
- **Asyncio-based**: All I/O operations use asyncio for concurrent process management
- **JSON-RPC 2.0**: Protocol for structured communication over Unix sockets
- **PID Journaling**: Fallback cleanup mechanism using `/tmp` for process tracking
- **Headless Operation**: Designed for automation and agentic workflows without GUI requirements
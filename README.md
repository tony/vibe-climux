# Climux

Climux runs and supervises background processes behind a JSON-RPC 2.0
server on a Unix domain socket, so a human at a terminal and a script or
AI agent can start, watch, and stop the same long-running command through
one interface. The server starts implicitly on the first command, like
`tmux` — there is nothing to launch by hand first.

Climux needs Python 3.12 or newer and a POSIX system: it listens on a
Unix domain socket, so it does not run on Windows. It has no runtime
dependencies — everything it does is standard library.

There is no installed console script yet. `climux.py` at the repository
root is the whole distribution; the sections below write `climux` for
readability, on the assumption it is on your `PATH` (see
[Quick Start](#quick-start)).

## Quick Start

```console
$ git clone https://github.com/tony/vibe-climux.git
```

```console
$ cd vibe-climux && uv sync --all-extras --dev
```

Put `climux.py` on your `PATH` as `climux`:

```console
$ ln -s "$(pwd)/climux.py" ~/.local/bin/climux
```

Or skip that and run it directly wherever a command below says `climux`:

```console
$ uv run python climux.py --help
```

Start a process, see it listed, read its output, then stop it. A fresh
process gets ID `1`, which `climux list` also reports:

```console
$ climux start python -m http.server 8000 --name webserver
```

```console
$ climux list
```

```console
$ climux logs 1
```

```console
$ climux stop 1
```

The server that started implicitly keeps running after this shell
session ends, ready for the next command — stop it by stopping every
process on its socket, or leave it; it costs nothing idle.

## Why Climux?

Local development means juggling one terminal per process — frontend,
backend, database, a test watcher — and losing track of which one just
printed an error. Climux gives every process a name and a single place
to check on, list, and restart them. Addressing is by ID — `climux list`
reports which ID belongs to which name — and `frontend` here is the
first process started, so it is ID `1`:

```console
$ climux start npm run dev --name frontend
```

```console
$ climux start python manage.py runserver --name backend
```

```console
$ climux start docker compose up postgres --name db
```

```console
$ climux tail 1
```

An AI agent cannot drive a terminal emulator reliably, but it can hold a
JSON-RPC connection and parse structured log entries. This lets an agent
start a task, keep reasoning about something else, and come back for the
result instead of blocking on it:

```python
import asyncio

from climux import ClimuxClient


async def deploy_and_watch(client: ClimuxClient) -> None:
    """Start a deploy, then poll its log until it finishes or errors."""
    deploy = await client.request(
        "start", {"command": ["./deploy.sh", "production"], "name": "deploy"}
    )
    while True:
        entries = await client.request("logs", {"id": deploy["id"], "lines": 10})
        for entry in entries:
            if "ERROR" in entry["content"]:
                raise RuntimeError(entry["content"])
            if "deploy complete" in entry["content"]:
                return
        await asyncio.sleep(5)
```

The same start-then-poll shape is what a CI bot driving several test
suites, a production-monitoring agent watching log output for anomalies,
or a coding assistant setting up a dev environment would build on top of
`client.request`.

## Core Features

- **Implicit server start.** The server starts on the first client
  command and persists after that client exits, like `tmux`.
- **JSON-RPC 2.0 over a Unix socket.** One typed request/response
  protocol for both the CLI and programmatic clients.
- **Named, addressable processes.** Give a process a name at start time;
  address it by the ID `climux list` reports.
- **Configurable log retention.** Each process buffers its own output —
  1000 lines or 24 hours by default, whichever limit is hit first.
- **stdin passthrough.** Send input to a running process's stdin from
  the CLI or over JSON-RPC.
- **PID journal cleanup.** A journal file survives a server crash, so
  the next server start reaps orphaned children before binding its
  socket.
- **No runtime dependencies.** The server, client, and CLI are one
  standard-library file.

## Usage

Read buffered output, most recent last; `--lines` caps how many:

```console
$ climux logs 1 --lines 50
```

`tail` returns the same buffered output as `logs` today — there is no
separate follow mode yet:

```console
$ climux tail 1
```

`snapshot` is `logs` with a smaller default (25 lines):

```console
$ climux snapshot 1
```

Send input to a process's stdin. A trailing newline is added
automatically if the data does not already end with one:

```console
$ climux send 1 y
```

Restart or stop by ID:

```console
$ climux restart 1
```

```console
$ climux stop 1
```

## Real-World Use Cases

### The "Full Stack Startup" Script

Save as `dev.sh`; running it starts the whole stack, `./dev.sh stop`
tears it down:

```bash
#!/bin/bash
# Climux starts automatically -- no setup needed.

climux start npm run dev --name frontend --cwd ./frontend
climux start python manage.py runserver --name api --cwd ./backend
climux start docker compose up postgres redis --name services
climux start python manage.py celery worker --name worker --cwd ./backend

echo "Dev environment ready. climux list / climux tail <id> to inspect it."

if [ "$1" = "stop" ]; then
    for id in $(climux list | cut -d']' -f1 | tr -d '['); do
        climux stop "$id"
    done
fi
```

### Debugging Production Issues Locally

```bash
export ENVIRONMENT=staging
climux start python app.py --name api
climux start node worker.js --name worker
climux start redis-server redis.prod.conf --name redis

climux send 1 trigger_bug_endpoint
climux logs 1 --lines 1000 > api_debug.log
```

### Microservices Development

Process control today is by the ID `climux list` reports, not by name —
start the batch, then check on all of them at once:

```bash
for service in auth user product cart payment shipping inventory \
    search recommendation analytics; do
    climux start npm run dev --name "$service" --cwd "./services/$service"
done
climux list
```

### One-Liner Dev Environment

```bash
alias dev='climux start npm run dev --name fe && climux start python api.py --name be && climux list'
alias dev-stop='climux list | cut -d"]" -f1 | tr -d "[" | xargs -I {} climux stop {}'
alias dev-logs='climux logs $(climux list | fzf | cut -d"]" -f1 | tr -d "[")'
```

### Git Hook for Automatic Testing

```bash
#!/bin/bash
# .git/hooks/pre-push
climux start pytest --name tests
climux start npm test --name js-tests

while climux list | grep -E "tests.*running"; do
    sleep 1
done

if climux logs 1 | grep -q "FAILED"; then
    echo "Tests failed, push aborted."
    exit 1
fi
```

### VSCode Task Integration

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start Dev Environment",
      "type": "shell",
      "command": "climux start npm run dev --name frontend",
      "problemMatcher": []
    },
    {
      // Replace 1 with the ID `climux list` reports for this process.
      "label": "View Backend Logs",
      "type": "shell",
      "command": "climux tail 1",
      "problemMatcher": []
    }
  ]
}
```

## Advanced Usage

### Socket Management

A named socket keeps environments apart — commands against one name
never see processes started against another. Each name gets its own
implicit server on first use, the same as the default socket does:

```console
$ climux -L dev start pytest --name tests
```

```console
$ climux -L test start pytest --name tests
```

```console
$ climux -L dev list
```

Running `climux server` directly (rather than letting a command start
one implicitly) runs the server in the foreground instead of
daemonizing — useful to watch its output, but it will not return until
stopped.

`-S path` points at a full socket path instead of a name in the default
directory, for when two environments must not even share that
directory.

### Process Configuration

`--cwd` sets a process's working directory; `--max-lines` and
`--max-hours` override the log-retention defaults (`0` or negative
disables that limit):

```console
$ climux start npm start --name frontend --cwd ./frontend --max-lines 5000
```

Environment variables are inherited the normal way — export before the
first command starts the server in this session, and every process it
spawns after that sees them:

```console
$ export API_KEY=secret
```

## Architecture

### Design Principles

Standard library only, asyncio for every I/O path, strict-mode mypy
across the source and tests, and processes that are guaranteed to be
cleaned up even after a server crash.

### Components

A `ClimuxServer` owns process state and answers JSON-RPC requests; a
`ClimuxClient` sends them over the socket. Each `ManagedProcess` keeps
its own log buffer and a `system`-sourced entry for lifecycle events
(started, exited, signal sent). A PID journal on disk lets the next
server start reap children an earlier, crashed server left running.

The server binds a Unix socket (default:
`<tempdir>/climux/default.sock`, where `<tempdir>` is
`tempfile.gettempdir()`; override with `-L name` or `-S path`) and
double-fork daemonizes so it outlives the client that started it. A
second client command against the same socket reuses that server rather
than starting another.

### Protocol

The CLI and any other client speak JSON-RPC 2.0 over that socket:

```json
{
  "jsonrpc": "2.0",
  "method": "start",
  "params": {
    "command": ["python", "app.py"],
    "name": "myapp"
  },
  "id": 1
}
```

## Development

### Setup

```console
$ git clone https://github.com/tony/vibe-climux.git
```

```console
$ cd vibe-climux && uv sync --all-extras --dev
```

The gates, the test suite, and pull request workflow are in
[CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Comparison with Alternatives

| Feature | Climux | tmux | pm2 | supervisord |
|---------|---------|------|-----|-------------|
| Headless operation | ✅ | ❌ | ✅ | ✅ |
| Zero dependencies | ✅ | ❌ | ❌ | ❌ |
| JSON-RPC control | ✅ | ❌ | ✅ | ❌ |
| Python native | ✅ | ❌ | ❌ | ✅ |
| Agent-friendly | ✅ | ❌ | ⚠️ | ⚠️ |
| Type-safe | ✅ | ❌ | ❌ | ❌ |

## Contributing

Prose and commit conventions are in [WRITING.md](.github/WRITING.md); the
full workflow is in [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

MIT License - see LICENSE file for details

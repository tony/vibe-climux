# Contributing

Thanks for looking. Climux is a young, single-file project — a bug report
with a reproduction, or a note on where a command's `--help` text misled
you, is the most useful thing you can send right now.

How this project writes prose — README, `CHANGES`, commit messages, CLI
help text and error messages, docstrings, and source comments — is set out
separately in [WRITING.md](WRITING.md). Read that before changing any of
it. The constraints every change is held to, and the map of what is where,
are in [AGENTS.md](../AGENTS.md).

## Getting set up

```console
$ uv sync --all-extras --dev
```

There is no installed console script yet — `climux.py` at the repository
root is the whole distribution. Run it as `./climux.py <command>` (it is
executable and carries a `#!/usr/bin/env python3` shebang) or
`uv run python climux.py <command>`.

## The gates

CI does not run these yet — there is no workflow in `.github/workflows/`
— so a green run of every command below, done locally, is what "done"
means until one exists.

Format:

```console
$ uv run ruff format .
```

Lint, applying autofixes:

```console
$ uv run ruff check . --fix --show-fixes
```

Type-check:

```console
$ uv run mypy
```

`[tool.mypy]` in `pyproject.toml` sets `strict = true` and scopes the check
to `climux.py` and `tests/`, so a bare `mypy` with no path argument already
checks the right files.

Test:

```console
$ uv run pytest
```

`ruff format` also reaches fenced Python code blocks inside Markdown
files — `README.md` today — so a documentation change that adds or edits
one is not done until `ruff format .` has run over it too.

Documented examples are a gate, not a courtesy, on whichever files are
wired up to run them. Which files that is today, and the one mistake that
silently removes a test, are in
[WRITING.md](WRITING.md#documented-examples-that-run).

Before claiming a test or a gate works, show it failing. A gate that has
never been red is an assumption.

## Tests

The suite is fully pytest-contained: fixtures spawn and tear down real
`ClimuxServer` instances, there is no external test runner or harness
script.

- **Isolation.** Every test gets its own Unix socket under a `tmp_path`
  fixture (`unique_socket_path`), named with the worker ID so
  `pytest -n auto` (pytest-xdist) does not collide two workers on one
  socket.
- **Two levels of server control.** `climux_server`/`climux_client`
  start a `ClimuxServer` in-process for fine-grained async control;
  `server_controller`/`cli_runner` shell out to `climux.py` as a real
  subprocess, for tests that need actual CLI behaviour rather than the
  library underneath it.
- **`process_factory`** starts a process and registers it for teardown,
  so a test that forgets to stop what it started does not leak a process
  into the next test.
- **`assert_process_cleanup`** uses `psutil` to snapshot Python
  processes before and after a test and fails it if any are left running.
- **Markers**: `slow`, `integration`, `stress` — deselect with
  `-m "not slow"`. `asyncio_mode = "auto"` autodetects `async def` tests;
  no `@pytest.mark.asyncio` needed.
- **`tmp_path_retention_policy = "failed"`** keeps `tmp_path` directories
  only for tests that failed, so a passing run does not accumulate temp
  files.

Run a single test:

```console
$ uv run pytest tests/test_climux.py::TestBasicOperations::test_server_ping
```

Run in parallel:

```console
$ uv run pytest -n auto
```

Watch mode, re-running on save:

```console
$ uv run pytest-watcher
```

## Releasing

Never create tags. Never push tags. The owner handles any release. See
[Release commits](WRITING.md#release-commits).

There is no CI-driven publish workflow and no prior release of this
project — that process does not exist yet to document.

## Pull requests

One subject per pull request. Unrelated cleanup found along the way
belongs in its own commit, and usually in its own pull request.

Discuss a substantial change via an issue before making it.

Merge once you have the sign-off of one other developer. Without
permission to merge yourself, ask a reviewer to merge it for you.

Commit format is in [WRITING.md](WRITING.md#commits).

## Decorum

- Participants will be tolerant of opposing views.
- Participants must ensure that their language and actions are free of
  personal attacks and disparaging personal remarks.
- When interpreting the words and actions of others, participants should
  always assume good intentions.
- Behaviour which can be reasonably considered harassment will not be
  tolerated.

Based on [Ruby's Community Conduct Guideline](https://www.ruby-lang.org/en/conduct/).

## Security

Please do not open a public issue for a vulnerability. There is no
`SECURITY.md` and no private reporting channel configured on this
repository yet — open an issue without exploit details and ask how to
reach a maintainer privately.

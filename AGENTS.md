# AGENTS.md

Climux is a headless CLI process manager: a single-file, stdlib-only Python
tool that runs background processes behind a JSON-RPC 2.0 server over a
Unix socket, with an implicit, tmux-like server start.

Follow the conventions already in the tree, and keep a change scoped to
what was asked for.

## What is here

| Path | What it is |
| ---- | ---------- |
| `climux.py` | Server, client, process manager, and CLI — the whole distribution |
| `tests/conftest.py` | Fixtures: server/client lifecycle, process factory, cleanup |
| `tests/test_climux.py` | Functional tests |
| `tests/test_edge_cases.py` | Edge-case and failure-path tests |
| `tests/test_server_lifecycle.py` | Implicit start, daemonization, attach/detach |
| `tests/test_helpers.py` | Debug helpers used by other test modules |
| `CHANGES` | Changelog |
| `.github/WRITING.md` | Prose policy |
| `.github/CONTRIBUTING.md` | Workflow policy |

## Which policy applies

- Documentation, user-facing text, `CHANGES`, commit messages, CLI help
  text and error messages, docstrings, and source comments:
  [.github/WRITING.md](.github/WRITING.md)
- Environment, the gates, tests, releases, and pull requests:
  [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)

Each of those is the single home for its subject. Where a rule seems to be
stated twice, the file listed above is the one that governs.

## Change discipline

- Make the smallest coherent change that solves the verified problem;
  keep unrelated cleanup out of it.
- Reuse an existing file, helper, API, or test before adding a new one.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized module — not for a
  single-use helper or a one-line re-export.
- Add a test for every user-visible behaviour change, and a `CHANGES`
  entry for every change to the CLI, the JSON-RPC surface, or output.
- A passing gate is evidence only once it has been shown capable of
  failing. Pair a new test with a deliberate break that proves it bites.

Climux has no external runtime dependencies; keep it that way unless
asked otherwise. There is no installed console script — run it directly
as `./climux.py <command>` or `uv run python climux.py <command>`.
`requires-python` is `>=3.12,<4.0`. The server starts implicitly on the
first client command and persists after the client exits, like tmux; a
change should not make the caller start it explicitly.

## References

- [Changelog](CHANGES)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)

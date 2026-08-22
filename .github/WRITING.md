# Writing

How this project writes prose, for humans and agents alike. It governs
`README.md`, `CHANGES`, commit messages, CLI help text and error messages,
docstrings, and source comments — every surface a reader reaches.

For environment setup, the gates, and pull request workflow, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Voice

Three surfaces, one voice. A docstring says what a caller may rely on; a
`CHANGES` entry says what changed; prose says what happens. All three are
present tense, lead with the thing being described, and stop. Why it was built
that way belongs in the commit message, which is timestamped and attached to
the diff.

The most useful editing operation is deleting the introductory sentence.

Lead with verbs and name concrete things. Put identifiers in backticks. Prefer
short declarative sentences, one operational fact each. Do not explain Python
to Python developers; do explain this project's semantics.

Type annotations describe shape. Documentation describes meaning. A sentence
that restates a signature has said nothing.

Use MUST, SHOULD, and MAY only where the normative sense is meant. Say what
actually happens rather than that something is "supported".

| Instead of                       | Prefer                            |
| --------------------------------- | ---------------------------------- |
| "We added…"                      | "`climux send` now accepts…"      |
| "New and improved"               | "`climux list` now…"              |
| "powerful", "seamless"           | state the capability              |
| "easily", "simply", "just"       | omit                              |
| "simple", "obvious", "intuitive" | omit                              |
| "robust"                         | name the failure that is handled  |
| "comprehensive"                  | name what is covered              |
| "production-ready"               | state the guarantee               |
| "optimized", "blazingly fast"    | give the magnitude                |
| "various fixes"                  | name the components               |
| "under the hood"                 | omit unless observable            |
| "please note that", "note that"  | state the fact                    |
| "leverage", "utilize"            | "use"                             |
| "delve into"                     | "read", or omit                   |
| "best practices"                 | name the practice                 |
| "in order to"                    | "to"                              |

## Who you are writing for

Climux has two readers. The default reader runs the CLI: they type `climux`
commands to manage local processes and want to know what a command does,
what it prints, and what a non-zero exit means. A second reader drives the
server programmatically, writing a JSON-RPC client — usually an AI agent, but
the protocol does not care who is on the other end. Serve the CLI reader
first; mark JSON-RPC material for the second reader so the first knows they
can stop reading.

Rules that follow:

- **Second person, present tense, active.** "You start a process", not "A
  process is started". Address the reader who is doing the thing.
- **Concept before API surface.** Open by saying what a command or method
  *does* for the reader. The flag list or JSON-RPC schema is the last detail
  they need, not the first.
- **Say when they can stop.** Lead with the default and the reassurance. Let
  a skimmer leave after one paragraph.
- **Grant permission, do not demand attention.** "Reach for this when…" tells
  readers they are in the right place without implying they must read on.
- **Progressive disclosure.** Order by how many readers need it: the common
  command, then the flag a few will tune, then the JSON-RPC method
  underneath. Each step is for a smaller audience than the last.
- **Name the trade-off.** If a call costs something — a process left running
  after the client exits, a log buffer that drops old lines — say so, and say
  what it buys.

## README

A README is the shortest path from "what is this?" to competent use, not the
project's autobiography.

The first sentence is a contract. It says what abstraction the reader has
been handed, concretely enough to tell this package apart from the
neighbouring one.

Get to a runnable command before anything the reader can skip. A logo, a
mission statement, a comparison matrix and three paragraphs of history in
front of the install line all cost the same thing.

State the minimum Python version and meaningful platform constraints in
prose, not only in badges. `requires-python` in `pyproject.toml` is the
authority; the README must agree with it.

Name the distribution, the import, and the executable separately wherever
they differ. That distinction prevents a Python-specific class of confusion —
and where no executable is installed yet, say what actually runs the tool
instead of writing a bare command name that fails.

Examples are executable, not illustrative fiction. Never
`your-command <some-options>`. See
[Documented examples that run](#documented-examples-that-run) for which
blocks are executed and how to write one that qualifies.

Document the semantic model, not the flag list. `--help` already enumerates
flags; what it cannot say is precedence, filesystem effects, what goes to
stdout versus stderr, and what a non-zero exit means.

State defaults explicitly — defaults are API. State negative guarantees
where they exist: "does not read your shell config", "no network access",
"never writes outside the socket directory". They establish boundaries
faster than any amount of description.

Headings stay conventional and stable, because people deep-link them.
Badges are few and load-bearing.

## CLI and error messages

`argparse` subcommand and argument `help=` strings are short imperative
fragments: capitalized, no trailing period, naming the thing acted on —
`"Start a new process"`, `"Process ID"`, `"Max log lines to keep"`. Match
this register; do not write full sentences into `help=`.

A client-side failure prints `Error: <message>` to stderr and exits `1`. A
failure the server reports over JSON-RPC reaches the client as
`RuntimeError("Server error: <message>")`, so the string a user sees is
`Error: Server error: <message>` — write server-side error text assuming
that prefix will be added, not assuming it stands alone.

JSON-RPC error codes follow the protocol's reserved ranges: `-32700` parse
error, `-32601` method not found, `-32603` internal error (uncaught
exception in request dispatch), `-32000` application error (a handler raised
on purpose — an unknown process ID, a missing required parameter). Reuse
`-32000` for a new handler-level failure rather than inventing a code in the
reserved range.

Log entries climux records for a managed process (visible through `climux
logs`, `climux tail`, `climux snapshot`) use the same register as CLI error
text: capitalized first word, no trailing period, naming the concrete fact —
`"Process started with PID 1234"`, `"Process exited with code 1"`. Keep new
entries in that voice so a log stream reads as one thing.

## Documented examples that run

Examples in this fleet are tests, where the repository's `pytest`
configuration makes them so. This section states what is actually
configured in climux today — read it before assuming the fleet-wide default
applies here.

**A fence tag is cosmetic. Only a `>>> ` prompt executes.** A block written
as

    ```python
    server = ClimuxServer(socket_path)
    ```

is prose that looks like a test. Nothing collects it, nothing runs it, and
it can be wrong for years. The same block written with prompts is a test:

    ```python
    >>> server = ClimuxServer(socket_path)
    ```

This is the single most expensive mistake available when editing
documentation, because removing the prompts leaves a green test suite and a
silently deleted test. When editing a file that contains examples, count the
prompts before and after.

**The fence tag is `python`.** Not `pycon`, not bare.

**What is configured, concretely.** `pyproject.toml` sets
`addopts = "... --doctest-modules --strict-markers"` and
`doctest_optionflags = "ELLIPSIS NORMALIZE_WHITESPACE"`, so any `>>> ` block
in a collected Python module runs with both flags active — `...` elides
variable output and whitespace differences do not fail a comparison.
`testpaths = ["tests"]`, so a bare `pytest` invocation only walks `tests/`.
`climux.py` sits at the repository root, outside `testpaths`, so a `>>> `
block added to its docstrings is **not** collected by a default `pytest`
run — running `pytest climux.py` explicitly, or adding `"climux.py"` to
`testpaths`, would be required first. `README.md` is not in `testpaths`, and
no Markdown or reStructuredText doctest collector (a plugin such as
`pytest-doctest-docutils`) is installed, so a `>>> ` block placed in
`README.md` executes nowhere today regardless of `testpaths` — `pytest`'s
built-in `--doctest-modules` only understands `.py` files.

**There are currently no `>>> ` blocks anywhere in this repository.** Adding
the first one to `climux.py` is a two-step change: write the example, and
extend `testpaths` (or invoke `pytest` with an explicit path) so it is
actually collected. Adding one to `README.md` additionally requires
installing and wiring a Markdown-doctest plugin — do not claim a Markdown
example runs without doing that first.

**No `doctest_namespace` fixture is defined.** A docstring example must
import everything it uses; nothing is injected automatically.

**`# doctest: +SKIP` is not permitted.** It is a workaround that tests
nothing.

**Do not downgrade a doctest to a non-executed block to make it pass.** A
`.. code-block::` or an unprompted fence does not run. If an example cannot
pass, fix the example or fix the code.

**Docstring examples** use the NumPy `Examples` section:

    Examples
    --------
    >>> config = ProcessConfig(command=["echo", "hi"])
    >>> config.name is None
    True

## The changelog

`CHANGES` is the changelog. Not `CHANGELOG.md`.

A ledger, not a narrative. It is scanned, and the question a reader is
asking is whether an entry affects them.

**Release entry boilerplate.** Every release header is
`## climux X.Y.Z (YYYY-MM-DD)`. The file opens with a
`## climux X.Y.Z (unreleased)` placeholder block fenced by
`<!-- KEEP THIS PLACEHOLDER ... -->` and `<!-- END PLACEHOLDER ... -->` HTML
comments — new entries land immediately below the END marker, never above
it.

**Unreleased entries carry no lead paragraph and no version summary.**
Speaking for a release — what the version "is", "ships", or "focuses on" —
is presumptuous before its scope is final. Only the person cutting the
release writes that. Never write or edit a lead paragraph from a feature
branch, and never ask or imply that a release should happen. Once a version
is cut, its lead opens with the version as sentence subject
(*"climux X.Y.Z ships …"*), two to four sentences on what shipped and who
cares, user-visible takeaways rather than internal mechanism.

**Each deliverable is a section, not a bullet.** Under a heading such as
`### What's new`, every distinct deliverable gets a
`#### Deliverable title (#NN)` heading naming it in user vocabulary,
followed by one to three prose paragraphs. Don't wrap a paragraph in `- ` —
bullets are for enumerable lists, not paragraph containers.

**The deliverable test.** Before writing an entry, ask: "What's the
deliverable, in user vocabulary?" If you can't answer in one sentence, the
entry isn't ready. Mechanism — helper internals, byte counters, where a
check lives — belongs in the commit message and code comments, not the
changelog.

**Fixed subheadings**, in this order when present: `### Breaking changes`,
`### Dependencies`, `### What's new`, `### Fixes`, `### Documentation`,
`### Development`. For a breaking change, show the migration path with a
concrete `# Before` / `# After` code block. Dependency floor bumps use the
form ``Minimum `pkg>=X.Y.Z` (was `>=X.Y.W`)``.

**PR refs `(#NN)`** sit in each deliverable's `####` heading.

**When bullets are appropriate.** A catch-all section (`### Fixes`,
occasionally `### Documentation`) with three or more genuinely small items
uses bullets — one line each, never paragraphs. If a bullet swells past two
lines, promote it to a `#### Title (#NN)` heading with a prose body.

**Anti-patterns.** Fragile metrics that go stale silently — token ceilings,
third-party version pins, percent benchmarks, exact byte counts. Describe
the capability, not the math. Private symbols (leading-underscore
identifiers) and internal jargon. Walls of text dressed up as bullets.
Breaking changes buried mid-entry instead of given their own subheading at
the top.

**Summarization style.** When asked "what changed in the latest version?",
lead with the entry's lead paragraph (paraphrased if needed), followed by
each `####` deliverable heading with a one-sentence summary. Cite `(#NN)`
only if asked for source links. Don't invent versions, dates, or numbers not
present in `CHANGES`.

## Docstrings

The prime directive: never restate the type. The annotation is the source
of truth; the docstring carries what the annotation cannot.

This is documentation debt wearing a docstring:

    def get_id(pane: Pane) -> str:
        """Get the pane's identifier.

        Parameters
        ----------
        pane : Pane
            The pane.

        Returns
        -------
        str
            The identifier.
        """

Document instead the dimensions the type system cannot encode:

- **Mutation.** What it changes in place.
- **Ordering.** Whether results come back in a guaranteed order.
- **Timing.** What has finished by the time the call returns, or the
  awaitable resolves.
- **Failure.** Which exceptions are raised and what triggers each.
- **Idempotence.** Whether calling twice does anything the second time.
- **Concurrency.** Whether calls are coalesced, queued, or independent.
- **Units and ranges.** What a number means and what values are accepted —
  a `0` or negative `max_log_lines`/`max_log_hours` disables the limit
  rather than raising.
- **Boundary behaviour.** What zero, empty, and the maximum do.
- **Security boundary.** What is executed, and what is only read.

The first sentence stands alone; tooling truncates there. PEP 257 applies:
triple double quotes, an imperative one-line summary ending in a period, a
blank line before any extended description. Do not repeat an
introspectable signature.

**Classes with fields** — `NamedTuple`, `@dataclass` — document every field
in an `Attributes` section:

```python
@dataclass
class LogEntry:
    """A single log entry with timestamp and content.

    Attributes
    ----------
    timestamp : datetime
        When the entry was recorded, in UTC.
    source : str
        Where the text came from: ``stdout``, ``stderr``, ``stdin`` for
        input echoed back on send, or ``system`` for climux's own
        lifecycle notes.
    content : str
        Line text, without the trailing newline.
    """
```

Autodoc-style tooling renders every field whether or not you describe it,
so an undocumented field ships bare to any generated reference. Document
all of them — a class with three fields and two documented still ships a
stub for the third.

## Source comments

A comment ships only if it passes all three gates. Fail any: delete or
rewrite. Borderline: delete — borderline means the information is
reconstructible, which is what makes deletion cheap.

**Loss.** Three years from now, would losing this cost a maintainer real
time rediscovering intent, an invariant, a constraint, or a failure mode
the code and tests do not already make obvious?

**Elite.** Would SQLite, Redis, the Go standard library, or CPython write
this comment, at this length? Those projects state the constraint and stop.
They do not argue with an imagined objector.

**Upkeep.** Will it stay true without maintenance? A comment that
hand-syncs a value the code owns — a count, an offset, a line reference, a
duplicated constant — is false the first time that value moves.

### Ceiling

One or two lines. A comment reaching four is either carrying several
facts, in which case split it, or arguing, in which case cut it to the
fact.

Rationale, alternatives weighed, and the story of how the code got here
belong in the commit message: timestamped, attached to the exact diff, and
free to maintain.

### Keep

- Why over how: upstream quirks, protocol and compatibility constraints,
  performance tradeoffs still part of the contract — for example, why
  `climux.py`'s blind-except and silent-`pass` handlers around process
  supervision and JSON-RPC dispatch carry per-file lint ignores instead of
  narrower exception types.
- Invariants, preconditions, ordering, lifetime, and concurrency
  requirements that types and tests cannot express.
- Code that looks wrong but is not, so a later cleanup does not
  reintroduce the bug.
- A high-level sketch of an algorithm whose local operations do not
  reveal the whole.

### Delete

- Narration of the next lines; code translated into English.
- Restated names, types, defaults, or control flow.
- Values duplicated from the code and hand-synced.
- Justification, hedging, or apology for a choice.
- Speculation about future requirements.
- History version control already holds, including commented-out code.
- Ticket and issue numbers. They say nothing to a reader without tracker
  access, and they rot when the tracker moves. Unfinished work goes in
  the tracker, not the source.
- Transient observations — "currently", "for now", "the latest release"
  — that go stale with no nearby edit.

### The upkeep gate in practice

It reaches values that track our own code. It does not reach frozen
external facts.

Bad (Delete):

```python
# There are 321 tests to complete for servers.
```

Good (Keep):

```python
# The journal is a cleanup aid, not a source of truth: a write failure
# here must not stop the server.
```

### Documentation exception

Minimal usage examples, and parameter, return, and raises entries on
public API are exempt from the loss gate — they serve the caller, not the
maintainer. They are exempt from nothing else. Ceiling: a good man page
entry.

## Terminology and capitalization

Pick the domain noun and keep it. A unit of work is a "process" everywhere
— not a "task" in one paragraph and a "job" in the next. The `id` a client
addresses it by is a "process ID"; do not alternate with "handle" or
"token".

Stable vocabulary is what makes search, deep links, and an agent's
retrieval work at all.

Python and PyPI keep their own capitalisation. Distribution names are
written as they are published.

Do not write counts into prose — how many commands exist, how many tests
there are. They go stale silently and no reader needs them.

## Markdown

Prose wraps at 80 columns. Table rows, badge lines, and long links are
exempt, because breaking them harms rendering. A pull request or issue body
does not wrap at all: GitHub renders a single newline as a space in a file
and as a line break in a comment, so a wrapped comment body arrives as
ragged stubs.

GitHub alert blocks — `> [!NOTE]`, `> [!WARNING]` — render as literal text
outside GitHub, so reserve them for at most one load-bearing warning per
document. Write the sentence so it carries the fact on its own, and a
renderer that drops the marker loses nothing.

Do not use a local absolute path or an email address in anything
published.

## Code blocks

Code blocks are paste-and-run units: pasting one block runs exactly one
intended action. Executed examples are exempt — the test suite runs them,
nobody pastes them. A multi-line script meant to be saved as a file (a
`dev.sh`, a git hook) is one block, because that is the one artifact a
reader copies.

- **One command per block.** Multiple steps may share a block only when
  explicitly chained with `&&`, `;`, or `\` continuations — the chain is
  then one logical command.
- **Explanations go in prose above the block**, never as `#` comments
  inside it.
- **Command menus are per-command blocks with prose lead-ins**, not
  tables.
- **Shell commands use the `console` tag with a `$ ` prefix.** This
  separates interactive commands from scripts and enables prompt-aware
  copy.
- **Split long commands with `\`** — one flag or flag+value pair per
  indented continuation line, positional arguments last.

Good — start a process and give it a name:

```console
$ climux start npm run dev --name frontend
```

Bad:

```console
# Start a process and give it a name, then list what's running
$ climux start npm run dev --name frontend && climux list
```

## Commits

```
Scope(type[detail]): concise description

why: Explanation of necessity or impact.

what:
- Specific technical changes made
- Focused on a single topic
```

Keep the subject to 50 characters or fewer, excluding any trailing `(#NN)`
pull request reference, and wrap body lines at 72. Separate the `why:` and
`what:` blocks with a blank line.

Routine maintenance commits drop the colon and take a capitalised
description, which is what distinguishes them at a glance in
`git log --oneline`:

```
py(deps[dev]) Bump dev packages
ai(rules[AGENTS]) Judge comments by three gates
```

Everything that changes behaviour keeps the colon.

Common types:

- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting
- **ci**: Workflow and pipeline changes
- **py(deps)**: Dependencies
- **py(deps[dev])**: Dev dependencies
- **ai(rules[AGENTS])**: AI rule updates

Example:

```
ProcessConfig(feat[env]): Add per-process environment overrides

why: Let a caller layer variables onto the server's environment
without exporting them for every process.

what:
- Add an env field to ProcessConfig
- Merge it onto os.environ.copy() before spawning
```

For a multi-line message, use a heredoc so the formatting survives:

```console
$ git commit -m "$(cat <<'EOF'
Scope(feat[detail]): Concise description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

### Release commits

Never create tags. Never push tags. The owner handles tagging and any
release. See [Releasing](CONTRIBUTING.md#releasing).

A release commit subject is plain and short: `Tag v<version>`. The
detailed why and what go in the body. Do not use the
`Scope(type[detail]):` format for a release — it buries the lede.

## Slop prevention

Treat AI slop as review-hostile noise, not as proof that text or code is
wrong. The goal is to maximise information density.

- **AI signatures.** No "Generated by", no conversational filler, no
  unexplained emoji, no tool metadata.
- **Brittle references.** No hard-coded line numbers, fragile file
  counts, dated "as of" claims, bare SHAs, or local absolute paths —
  unless they are strict evidentiary artefacts such as a benchmark log.
- **Diff narration.** Do not restate what moved, was renamed, or was
  removed in anything the reader holds alongside the diff: code,
  docstrings, README, `CHANGES`, or a pull request description. The diff
  and the commit message already carry it.
- **Branch-internal narrative.** Do not mention intermediate states,
  abandoned approaches, or "no longer" behaviour unless users of a
  published release actually experienced the old state. Use trunk, not an
  intermediate state on the current branch, as the baseline for that
  question.
- **Low-value scaffolding.** No ownerless TODOs, unused
  future-proofing, debug artefacts, or defensive wrappers around failure
  modes nothing can reach.
- **Prose inflation.** The diction table under [Voice](#voice) governs;
  replace an inflated word with a concrete description of behaviour,
  constraints, or trade-offs.
- **Coded labels.** Write rules and findings as plain imperatives. No
  `[R1]`, `Option B`, or any index a reader has to decode.

Preserve the "why". Never delete a comment documenting an invariant, a
protocol constraint, a platform quirk, or an upstream workaround — those
are the facts [Source comments](#source-comments) keeps, and every other
comment is judged by it.

### Durable source links

Link to a pinned revision, never to trunk. A pinned permalink is not a
brittle reference; an unlinked SHA dropped into prose is. `blob/main/…`
links rot silently — the file moves, lines shift, and the anchor lands on
unrelated code while still resolving.

- Prefer a release tag (`blob/v0.1.0/…`) once one exists. Most durable,
  and it tells the reader which released version the claim held for.
- Otherwise use a 7-char commit ref (`blob/9a29b1a/…`) reachable from
  trunk. Never a PR-head SHA — it can be rebased or garbage-collected.
- Reserve `blob/main/…` for living documents meant to always show the
  latest state, such as this file.
- Line anchors (`#L120-L145`) are only safe on a pinned ref.

### Cleanup in hindsight

When applying these rules retroactively from inside a feature branch,
first establish scope by diffing against trunk to identify which commits
this branch actually introduced. For in-branch commits, either fold the
fix into `fixup!` commits addressed with `git rebase --autosquash`, or
land a single cleanup commit at branch tip. Leave trunk commits alone
unless the user explicitly opts in to touching shared history.

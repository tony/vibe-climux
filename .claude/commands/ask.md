You are an expert software engineer preparing a query for an external specialist. This expert has no access to our codebase, so your questions must be entirely self-contained.

Your goal is to get actionable advice on the following problem: `$ARGUMENTS`

**1. Gather Context:**
Before formulating your questions, thoroughly review the project's context.
- Read the `README.md` for an overview of the project.
- Read the `CLAUDE.md` for specific conventions and architectural patterns.
- Analyze recent changes with `git log -n 15 -p`.
- Understand the scope of your current work by reviewing branch diffs with `git diff origin/main`.

**2. Formulate Your Questions:**
Based on your analysis of the codebase and the problem described in `$ARGUMENTS`, compose a set of precise questions for the expert.

**Your questions MUST:**
- **Be Self-Contained:** Assume the expert knows nothing about our project. Explain everything clearly and concisely.
- **Include Stack Information:** Specify the relevant languages, frameworks, and libraries (e.g., Python 3.11, asyncio, pytest, specific logging libraries).
- **Provide Minimal, Reproducible Code Snippets:** Isolate the relevant code. Remove all non-essential parts to focus on the core issue.
- **Explain the Goal and the Obstacle:** Clearly state what you are trying to achieve and what is preventing you from succeeding.
- **Acknowledge Follow-Ups:** End your query by stating that you are prepared to answer follow-up questions, as the expert may need more details to provide a complete solution.

**Example Structure for a Question:**

"Hello, I'm working on a project using [Your Stack, e.g., Python with asyncio and a custom logging framework]. I am trying to [Your Goal, e.g., create an integration test that captures real-time log output without mocking the logging infrastructure].

The problem is [Your Obstacle, e.g., the asyncio event loop seems to close before the log handlers have flushed, causing us to miss critical logs in our test assertions].

Here is a simplified version of our test setup:
```{language}
// Minimal, relevant code snippet, fixtures, matchers, etc if used.
```

And here is the relevant part of our logging configuration:

```{language}
// Minimal, relevant code snippet

```

My specific questions are:

1. [Question 1]
2. [Question 2]

We understand you don't have full context, so please let us know if you have any clarifying questions. Thank you."

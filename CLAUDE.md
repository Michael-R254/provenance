# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Start each session by reading `docs/milestones.md` and finding the milestone you were asked to
  work on. Do not start the next milestone unless asked.
- Use plan mode for anything touching more than a few files. Show the plan before editing.
- Keep the todo list in sync with the milestone's acceptance criteria, and tick each one only after
  its check has actually run.
- Before finishing, run the full command block in AGENTS.md and paste a short summary of results.
- Never run commands that call paid APIs (Anthropic) unless Michael explicitly asks in this
  session. Use `MockProvider` or `OllamaProvider`.
- Never push to `main`. Open a pull request from the milestone branch and stop for review.
- If you notice a fact about Michael in code or content that is not backed by a file in `content/`,
  flag it rather than "fixing" it with your own wording.

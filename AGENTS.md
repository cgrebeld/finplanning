# Agent Instructions

## Repository Graph

This project has a local Graphify knowledge graph in `graphify-out/`.

- Before broad architecture, dependency, call-path, or change-impact searches, query the graph.
- Prefer the Graphify MCP tools when available: start with `query_graph`, then use
  `get_neighbors`, `shortest_path`, `god_nodes`, or `get_pr_impact` for narrower
  questions.
- The portable CLI fallback is `./finplan-graph`. Run
  `./finplan-graph query "<question>"`, `path "<A>" "<B>"`, or
  `explain "<concept>"`.
- If the graph is missing, run `./finplan-graph build`. After code changes and
  the project's required quality checks, run `./finplan-graph update`.
- Treat `EXTRACTED` edges as navigation evidence. Verify `INFERRED` or
  `AMBIGUOUS` relationships in source and tests before changing code.
- The graph accelerates discovery; source code, tests, and project documentation
  remain authoritative. Fall back to `rg` when the graph lacks precise detail.

## Committing Work

- Commit each substantial, self-contained chunk of work (a fix, a feature, a
  refactor) once it passes the project's quality checks. Do not leave finished
  changes uncommitted at the end of a task.
- Keep commits focused: stage only the files you changed for that chunk, and
  never sweep in unrelated untracked files.
- Never commit directly on `main`; branch first if needed.
- The remote tracks only `main`. Before pushing, merge the finished branch back
  into `main` locally, then push `main`. Never push feature branches, and delete
  the merged local branch afterwards.

## Subagent Model Policy

When delegating independent work:

- Use `gpt-5.6-sol` with high effort for architecture, cross-cutting or
  security-sensitive changes, difficult debugging, and integration review.
- Use `gpt-5.6-terra` with medium effort for focused implementation, tests,
  documentation, and repository exploration.
- Keep the coordinating agent on `gpt-5.6-sol` with high or higher effort.
- If model override is unavailable in the current Codex workflow, inherit the
  coordinator's model rather than attempting unsupported configuration changes.

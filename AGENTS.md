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

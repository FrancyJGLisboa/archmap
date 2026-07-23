# archmap

**Ask your agent to map your codebase. The HTML is for you. The JSON is for the next agent.**

archmap is a universal agent skill — plain markdown instructions any agentic
runtime can follow (Claude Code, GitHub Copilot CLI, Cursor, Codex, or a chat
window). It produces two artifacts from any repo:

- `docs/architecture/architecture.json` — a **fixed, versioned schema** (v1)
  the next agent can program against: layers, components, dependencies,
  external services, end-to-end flows, entry points.
- `docs/architecture/architecture.html` — a **self-contained interactive
  viewer** (zero external requests): layers as columns, flows in a sidebar,
  click a flow to highlight its path through the system.

The HTML is rendered *from* the JSON — one source of truth, the two can't
disagree. And unlike the viral version of this idea, archmap has a staleness
answer: the JSON records the git commit it was generated at, and the skill
tells consuming agents to `git diff` against it before trusting anything.
**The map is a cache with a cache key, not gospel.**

## Install

**Claude Code**
```bash
git clone https://github.com/FrancyJGLisboa/archmap ~/.claude/skills/archmap
```

**GitHub Copilot CLI / Cursor / Codex / others**
Clone anywhere, then point your rules file (`AGENTS.md`, `.cursor/rules`,
`.github/copilot-instructions.md`, …) at `SKILL.md` — or paste `SKILL.md`
into context. On runtimes that can't execute scripts, the skill degrades
gracefully: the validation rules are restated in prose and the agent
self-checks them.

## Use

Ask your agent:

> Map this repo's architecture with archmap.

To consume an existing map safely:

> Check whether the archmap is stale, then tell me how a request flows
> through the system.

## Enforcement, not vibes

`scripts/validate.py` (Python 3 stdlib, no dependencies) hard-fails maps that
try to cheat:

| Check | Blocks |
|---|---|
| Schema v1, ≥5 components, ≥2 flows, no dangling ids | minimal-but-valid stubs |
| Every `component.path` exists on disk | invented paths |
| ≥80% of top-level source dirs claimed; `"."` forbidden | catch-all components |
| HTML data block equals the JSON; no external resources | hardcoded demo HTML |
| `generated.commit_sha` == live `git rev-parse HEAD` | stale maps |

```bash
python3 scripts/validate.py docs/architecture/ --root .
```

The full loss function, including how each check could be gamed and what
prevents it, is in [`eval/checks.yaml`](eval/checks.yaml).

## Example

[`examples/yt2md/`](examples/yt2md/) maps
[yt2md](https://github.com/FrancyJGLisboa/yt2md) end-to-end — open
`architecture.html` in a browser and click the flows.

## Files

- [`SKILL.md`](SKILL.md) — the skill (producer + consumer paths)
- [`schema/architecture.schema.json`](schema/architecture.schema.json) — JSON Schema v1
- [`assets/viewer.html`](assets/viewer.html) — viewer template
- [`scripts/validate.py`](scripts/validate.py) — validator
- [`eval/checks.yaml`](eval/checks.yaml) — loss function

## License

MIT

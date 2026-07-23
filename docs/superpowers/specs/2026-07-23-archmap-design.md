# archmap — Design Spec

**Date:** 2026-07-23
**Status:** Approved by Francy (design conversation, 2026-07-22/23)

## What

A universal, cross-runtime agent skill that maps a codebase's architecture into
two artifacts:

- `docs/architecture/architecture.json` — a fixed, versioned, machine-readable
  contract for the *next agent* working on the repo.
- `docs/architecture/architecture.html` — a self-contained interactive viewer
  for humans, rendered *from* the JSON (single source of truth).

Inspired by Vivek Sen's tweet (2026-07-21): "The HTML is for you. The JSON is
for the next agent. Your codebase now explains itself."

## Decisions (settled with Francy)

1. **Audience:** public open-source. GitHub repo installable into Claude Code,
   Copilot CLI, Cursor, Codex — or pasted into any chat.
2. **Portability:** one `SKILL.md` (Agent Skills markdown format) + bundled
   scripts as **progressive enhancement**. The skill MUST work pure-prompt on
   runtimes that forbid script execution; scripts add determinism where
   allowed.
3. **JSON contract:** fixed versioned schema (`architecture.schema.json`, v1)
   with an `x_extensions` free-form block for domain specifics.
4. **HTML:** fixed viewer template shipped with the skill; the generating agent
   only injects the repo's JSON into one data block. The HTML cannot disagree
   with the JSON because it is a viewer over it.
5. **Staleness:** the JSON records `generated.commit_sha`. The map is a cache
   with a cache key, not gospel — consumer instructions (below) make the next
   agent verify before trusting.

## Repo layout

```
archmap/
  SKILL.md                          # the universal skill — pure prompt, works anywhere
  schema/architecture.schema.json   # versioned contract (v1)
  assets/viewer.html                # self-contained viewer; <script id="archmap-data"> injection point
  scripts/validate.py               # stdlib-only Python 3; optional enhancement
  eval/checks.yaml                  # loss function (below), goodhart-gate format
  README.md                         # install per runtime + example screenshot
  docs/superpowers/specs/           # this spec
```

## Workflow SKILL.md instructs (producer side)

1. **Scan** the target repo: entry points, packages/modules, external services,
   build/deploy paths. Read manifests (package.json, pyproject.toml, go.mod,
   render.yaml, Dockerfile, CI configs) before reading code.
2. **Write** `docs/architecture/architecture.json` conforming to schema v1,
   including `generated: {commit_sha, branch, date, tool_version}`.
3. **Validate:** run `scripts/validate.py docs/architecture/` if the runtime
   allows execution; otherwise self-check inline against the schema rules
   restated in SKILL.md (progressive-enhancement fallback).
4. **Render:** copy `assets/viewer.html` to
   `docs/architecture/architecture.html`, replacing the contents of
   `<script id="archmap-data" type="application/json">` with the JSON.

## Consumer section (in SKILL.md, addressed to the next agent)

Before trusting the map: run `git diff --stat <generated.commit_sha>..HEAD`.
Files under a component's `path` changed → that component is stale; re-scan it
(or regenerate fully if many components are stale). Never answer architecture
questions from a stale component without saying so.

## Schema v1 core

- `archmap_version` (const "1")
- `name`, `description`
- `generated: {commit_sha, branch, date, tool_version}`
- `layers[]: {id, name, order}` — columns in the viewer
- `components[]: {id, name, layer, path, description, tech, dependencies[]}`
  — `path` is repo-relative and must exist; `dependencies` reference component ids
- `external_services[]: {id, name, description, url?}`
- `flows[]: {id, name, description, steps[{from, to, label}]}` — from/to
  reference component or external-service ids; clicking a flow in the viewer
  highlights its path
- `entry_points[]: {component, description}`
- `x_extensions` — free-form object, ignored by the viewer and validator

## Viewer requirements

Self-contained single file: zero external requests (no CDN, no fonts, no
fetch). Column layout by layer, flow list in a sidebar, clicking a flow
highlights the step path with numbered badges (the tweet's demo interaction).
Light/dark via `prefers-color-scheme`. Vanilla JS + inline CSS only.

## Validator (`scripts/validate.py`, stdlib only)

Checks, in order — any failure = exit 1 with a one-line reason:

1. JSON parses and conforms to schema v1 (hand-rolled checks, no jsonschema dep).
2. ≥5 components, ≥2 flows; every dependency/flow step references a declared id.
3. Every `component.path` exists on disk (run from repo root).
4. Coverage: ≥80% of top-level source directories claimed by some component
   path; reject a path of "." or any single path claiming >50% of the tree at
   depth <1.
5. HTML data block byte-equals `architecture.json` (after JSON normalization).
6. `generated.commit_sha` equals `git rev-parse HEAD` (skipped with a warning
   if not a git repo or SHA check explicitly waived via `--no-git`).

## Loss function

checks:
  - check: architecture.json passes scripts/validate.py (schema v1, exit 0)
    false_pass: agent emits minimal-but-valid JSON (2 components, no flows)
    mitigation: validator enforces >=5 components, >=2 flows, every flow step references a declared component id
  - check: every component.path exists on disk in the target repo
    false_pass: agent invents plausible paths
    mitigation: validator stats each path; nonexistent path = hard fail
  - check: viewer HTML renders offline and embedded JSON equals architecture.json
    false_pass: agent hardcodes demo data into the HTML
    mitigation: validator extracts the embedded block and diffs against the .json file
  - check: coverage >=80% of top-level source dirs claimed by some component.path
    false_pass: one catch-all component with path "."
    mitigation: validator rejects "." and any depth<1 path claiming >50% of tree
  - check: generated.commit_sha equals repo HEAD at generation time
    false_pass: agent copies a stale SHA from an old run
    mitigation: validator compares against live `git rev-parse HEAD`
holdout: run the finished skill on ~/noticiasagricolasbr (never used during the
  build loop) and Francy eyeballs the HTML — never automated, never trained against

## Testing

- Unit: validator tested against a known-good fixture JSON + mutations (missing
  field, dangling dep id, fake path, stale SHA, tampered HTML block).
- Dogfood: run the skill end-to-end on `~/yt2md` (small) and `~/russia_crop_etl`
  (medium) during development.
- Holdout: `~/noticiasagricolasbr`, human-judged only.

## Out of scope (v1)

- Auto-regeneration hooks / CI integration (consumer instructions cover staleness)
- Multi-repo / monorepo-workspace stitching
- Rendering diagrams to PNG/PDF
- Language-specific static analysis; the mapping is agent-read, not parsed

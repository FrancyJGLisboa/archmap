---
name: archmap
description: Map a codebase's architecture into two artifacts — docs/architecture/architecture.json (fixed schema v1, for the next agent) and docs/architecture/architecture.html (self-contained interactive viewer, for humans). Use when asked to map, document, or visualize a repo's architecture, to onboard an agent or human to an unfamiliar codebase, or before substantial cross-cutting work. Also defines how to CONSUME an existing map safely (staleness check against generated.commit_sha).
---

# archmap

Two artifacts, one source of truth. The HTML is for humans. The JSON is for
the next agent. The JSON records the git commit it was generated at — it is a
cache with a cache key, not gospel.

## If the map already exists (consumer path — read this FIRST)

Before trusting `docs/architecture/architecture.json`:

1. Read `generated.commit_sha` from the JSON.
2. Run `git diff --stat <commit_sha>..HEAD`.
3. If changed files fall under any component's `path`, that component is
   STALE. Re-scan those components before relying on them; if many are stale,
   regenerate the whole map (producer path below).
4. Never answer architecture questions from a stale component without saying
   it is stale.

## Producing the map

### 1. Scan

Read manifests before code: `package.json`, `pyproject.toml`, `go.mod`,
`Cargo.toml`, `Dockerfile`, `render.yaml`, CI configs, infra-as-code. Then
identify: entry points, top-level packages/modules, external services
(APIs, DBs, queues, third-party SaaS), and 3-8 end-to-end flows a developer
would actually trace (a request, a build, a deploy, a signup).

### 2. Write `docs/architecture/architecture.json`

Conform to schema v1 (`schema/architecture.schema.json` in this skill's
directory). Shape:

- `archmap_version`: `"1"`
- `name`, `description`
- `generated`: `{commit_sha, branch, date, tool_version}` — commit_sha MUST
  be the current `git rev-parse HEAD` of the target repo
- `layers[]`: `{id, name, order}` — rendered as columns, left to right
- `components[]`: `{id, name, layer, path, description, tech, dependencies[]}`
  — `path` is repo-relative and MUST exist; never `"."`
- `external_services[]`: `{id, name, description, url}`
- `flows[]`: `{id, name, description, steps[{from, to, label}]}` — from/to
  reference component or external-service ids
- `entry_points[]`: `{component, description}`
- `x_extensions`: free-form object for anything domain-specific

### 3. Validate

If this runtime can execute scripts, run (from the target repo root):

    python3 <skill-dir>/scripts/validate.py docs/architecture/

Fix every FAIL and re-run until it prints `OK`.

If scripts cannot run here, self-check the SAME rules inline:

- required fields present; `archmap_version == "1"`
- >= 5 components, >= 2 flows
- ids unique; every dependency and flow step references a declared id;
  every component's layer is declared
- every `component.path` exists on disk; no `"."`, no absolute paths, no `..`
- >= 80% of top-level source directories (ignore docs/tests/build/vendor
  dirs) are claimed by some component path
- `generated.commit_sha` equals current `git rev-parse HEAD`
- the HTML data block byte-matches the JSON (step 4)

### 4. Render `docs/architecture/architecture.html`

Copy `assets/viewer.html` from this skill's directory, then replace ONLY the
contents of `<script id="archmap-data" type="application/json">…</script>`
with the exact contents of `architecture.json`. Do not edit anything else in
the template. The viewer renders layers as columns, flows in a sidebar, and
highlights a flow's path when clicked.

## Rules

- Do not invent paths, components, or services — everything in the JSON must
  be verifiable in the repo. If unsure a service is used, grep for it first.
- Keep descriptions to one sentence; the map is navigation, not documentation.
- Put domain-specific extras in `x_extensions`, never as new top-level fields.
- Regenerate rather than hand-edit drifted maps.

# archmap

This repo ships one agent skill: **archmap** — it maps a codebase's
architecture into two artifacts with one source of truth:

- `docs/architecture/architecture.json` — fixed schema v1, machine-readable,
  for the next agent working on the repo
- `docs/architecture/architecture.html` — self-contained interactive viewer,
  for humans

**When to use it:** the user asks to map, document, or visualize a repo's
architecture; an agent or human needs onboarding to an unfamiliar codebase;
or substantial cross-cutting work is about to start.

**How:** follow `skills/archmap/SKILL.md` exactly. It contains both paths:

- **Consumer path** (read first): before trusting an existing
  `architecture.json`, check `generated.commit_sha` against `git diff` — the
  map is a cache with a cache key, not gospel. Never answer architecture
  questions from a stale component without saying so.
- **Producer path**: scan manifests before code, write the JSON to schema v1
  (`skills/archmap/schema/architecture.schema.json`), validate with
  `python3 skills/archmap/scripts/validate.py docs/architecture/ --root .`
  (or self-check the rules restated in SKILL.md if scripts can't run here),
  then inject the JSON into `skills/archmap/assets/viewer.html`.

**Hard rules:** never invent paths, components, or services — everything in
the map must be verifiable in the repo. Fix every validator FAIL before
presenting the map.

(Agents working on the archmap repo itself: run the test suite with
`uv run --with pytest pytest tests/ -v` and keep `SKILL.md`'s prose rules in
sync with `validate.py`'s enforced thresholds — the tests check this.)

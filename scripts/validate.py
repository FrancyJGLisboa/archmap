#!/usr/bin/env python3
"""archmap validator — Python 3 stdlib only.

Usage: validate.py <architecture.json|dir> [--root REPO] [--html PATH] [--no-git]
Exit 0 = valid, 1 = invalid, 2 = usage error.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MIN_COMPONENTS = 5
MIN_FLOWS = 2
COVERAGE_THRESHOLD = 0.8
NON_SOURCE_DIRS = {
    "docs", "doc", "test", "tests", "node_modules", "vendor", "dist", "build",
    "target", "venv", "__pycache__", "coverage", "tmp", "examples", "fixtures",
}
DATA_BLOCK_RE = re.compile(
    r'<script id="archmap-data" type="application/json">(.*?)</script>', re.S
)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"WARN: {msg}")


def ids_of(items: list, kind: str) -> set:
    ids = [i.get("id") for i in items]
    if len(ids) != len(set(ids)):
        fail(f"duplicate {kind} ids")
    return set(ids)


def check_structure(data: dict) -> None:
    for field in ("archmap_version", "name", "generated", "layers", "components", "flows"):
        if field not in data:
            fail(f"missing required field '{field}'")
    if data["archmap_version"] != "1":
        fail(f'archmap_version must be "1", got {data["archmap_version"]!r}')
    for field in ("commit_sha", "branch", "date"):
        if field not in data["generated"]:
            fail(f"generated missing '{field}'")
    comps, flows = data["components"], data["flows"]
    ext = data.get("external_services", [])
    if len(comps) < MIN_COMPONENTS:
        fail(f"need >={MIN_COMPONENTS} components, got {len(comps)}")
    if len(flows) < MIN_FLOWS:
        fail(f"need >={MIN_FLOWS} flows, got {len(flows)}")
    layer_ids = ids_of(data["layers"], "layer")
    comp_ids = ids_of(comps, "component")
    ext_ids = ids_of(ext, "external_service")
    shared = comp_ids & ext_ids
    if shared:
        fail(f"ids shared between components and external_services: {sorted(shared)}")
    node_ids = comp_ids | ext_ids
    for c in comps:
        for field in ("id", "name", "layer", "path", "description"):
            if not c.get(field):
                fail(f"component {c.get('id', '?')!r} missing '{field}'")
        if c["layer"] not in layer_ids:
            fail(f"component {c['id']!r} references unknown layer {c['layer']!r}")
        for dep in c.get("dependencies", []):
            if dep not in node_ids:
                fail(f"component {c['id']!r} depends on unknown id {dep!r}")
    for f in flows:
        for field in ("id", "name", "steps"):
            if not f.get(field):
                fail(f"flow {f.get('id', '?')!r} missing '{field}'")
        for i, s in enumerate(f["steps"]):
            for end in ("from", "to"):
                if s.get(end) not in node_ids:
                    fail(f"flow {f['id']!r} step {i} references unknown id {s.get(end)!r}")


def check_paths(data: dict, root: Path) -> None:
    for c in data["components"]:
        p = c["path"]
        if p in (".", "", "/") or p.startswith("/") or ".." in Path(p).parts:
            fail(f"component {c['id']!r} has forbidden path {p!r}")
        if not (root / p).exists():
            fail(f"component {c['id']!r} path does not exist: {p}")


def check_coverage(data: dict, root: Path) -> None:
    src_dirs = {
        d.name for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in NON_SOURCE_DIRS
    }
    if not src_dirs:
        return
    claimed = {
        Path(c["path"]).parts[0]
        for c in data["components"]
        if Path(c["path"]).parts[0] in src_dirs
    }
    ratio = len(claimed) / len(src_dirs)
    if ratio < COVERAGE_THRESHOLD:
        fail(f"coverage {ratio:.0%} < {COVERAGE_THRESHOLD:.0%} — "
             f"unclaimed top-level dirs: {sorted(src_dirs - claimed)}")


def check_html(data: dict, html_path: Path) -> None:
    if not html_path.exists():
        fail(f"html not found: {html_path}")
    text = html_path.read_text(encoding="utf-8")
    m = DATA_BLOCK_RE.search(text)
    if not m:
        fail('html has no <script id="archmap-data"> block')
    try:
        embedded = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        fail(f"embedded JSON does not parse: {e}")
    if embedded != data:
        fail("embedded JSON differs from architecture.json")
    stripped = DATA_BLOCK_RE.sub("", text)
    if re.search(r'\b(?:src|href)\s*=\s*["\']https?://', stripped):
        fail("html references external resources")


def check_git(data: dict, root: Path) -> None:
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        warn("not a git repo (or git missing) — skipping SHA check")
        return
    sha = data["generated"]["commit_sha"]
    if head != sha:
        fail(f"generated.commit_sha {sha[:12]} != HEAD {head[:12]} — map is stale, regenerate")


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate archmap artifacts.")
    ap.add_argument("json_path", type=Path, help="architecture.json (or its directory)")
    ap.add_argument("--root", type=Path, default=Path("."), help="target repo root")
    ap.add_argument("--html", type=Path, default=None,
                    help="architecture.html (default: sibling of the json)")
    ap.add_argument("--no-git", action="store_true", help="skip commit_sha == HEAD check")
    args = ap.parse_args()

    json_path = args.json_path
    if json_path.is_dir():
        json_path = json_path / "architecture.json"
    if not json_path.exists():
        fail(f"not found: {json_path}")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"architecture.json does not parse: {e}")

    root = args.root.resolve()
    check_structure(data)
    check_paths(data, root)
    check_coverage(data, root)
    check_html(data, args.html or json_path.with_name("architecture.html"))
    if args.no_git:
        warn("--no-git: skipping SHA check")
    else:
        check_git(data, root)
    print("OK: archmap artifacts valid")


if __name__ == "__main__":
    main()

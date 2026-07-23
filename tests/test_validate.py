"""Tests for scripts/validate.py — run via: uv run --with pytest pytest tests/ -v"""
import json
import re
import subprocess
import sys
from pathlib import Path

VALIDATE = Path(__file__).resolve().parent.parent / "scripts" / "validate.py"


def good_data():
    return {
        "archmap_version": "1",
        "name": "demo",
        "description": "Demo app",
        "generated": {"commit_sha": "a" * 40, "branch": "main", "date": "2026-07-23"},
        "layers": [
            {"id": "interface", "name": "Interface", "order": 1},
            {"id": "core", "name": "Core", "order": 2},
        ],
        "components": [
            {"id": "cli", "name": "CLI", "layer": "interface", "path": "cli/main.py",
             "description": "Command line entry", "tech": "python", "dependencies": ["api"]},
            {"id": "helpers", "name": "CLI helpers", "layer": "interface", "path": "cli/helpers.py",
             "description": "Arg parsing", "tech": "python", "dependencies": []},
            {"id": "api", "name": "API", "layer": "core", "path": "src/api.py",
             "description": "HTTP API", "tech": "python", "dependencies": ["store"]},
            {"id": "store", "name": "Store", "layer": "core", "path": "src/store.py",
             "description": "Persistence", "tech": "python", "dependencies": []},
            {"id": "app", "name": "App", "layer": "core", "path": "src/app.py",
             "description": "Wiring", "tech": "python", "dependencies": ["api", "weather"]},
        ],
        "external_services": [
            {"id": "weather", "name": "Weather API", "description": "3rd party",
             "url": "https://example.com"},
        ],
        "flows": [
            {"id": "f1", "name": "CLI query", "description": "User runs CLI",
             "steps": [{"from": "cli", "to": "api", "label": "invoke"},
                       {"from": "api", "to": "store", "label": "read"}]},
            {"id": "f2", "name": "External fetch", "description": "App pulls weather",
             "steps": [{"from": "app", "to": "weather", "label": "GET"}]},
        ],
        "entry_points": [{"component": "cli", "description": "python -m cli"}],
        "x_extensions": {},
    }


def make_repo(tmp_path, data=None):
    """Build a fake target repo satisfying `data` (default good_data())."""
    data = data if data is not None else good_data()
    for rel in ("cli/main.py", "cli/helpers.py", "src/api.py", "src/store.py", "src/app.py"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# stub\n")
    out = tmp_path / "docs" / "architecture"
    out.mkdir(parents=True, exist_ok=True)
    (out / "architecture.json").write_text(json.dumps(data, indent=2))
    (out / "architecture.html").write_text(
        '<!doctype html><html><body><script id="archmap-data" '
        'type="application/json">' + json.dumps(data) + "</script></body></html>"
    )
    return out / "architecture.json"


def run_validate(json_path, root, *extra):
    return subprocess.run(
        [sys.executable, str(VALIDATE), str(json_path), "--root", str(root), *extra],
        capture_output=True, text=True,
    )


def test_good_repo_passes(tmp_path):
    jp = make_repo(tmp_path)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_missing_required_field_fails(tmp_path):
    data = good_data()
    del data["layers"]
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "layers" in r.stdout


def test_too_few_components_fails(tmp_path):
    data = good_data()
    data["components"] = data["components"][:2]
    data["flows"] = [
        {"id": "f1", "name": "A", "steps": [{"from": "cli", "to": "helpers", "label": "x"}]},
        {"id": "f2", "name": "B", "steps": [{"from": "helpers", "to": "cli", "label": "y"}]},
    ]
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert ">=5" in r.stdout


def test_too_few_flows_fails(tmp_path):
    data = good_data()
    data["flows"] = data["flows"][:1]
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert ">=2" in r.stdout


def test_dangling_dependency_fails(tmp_path):
    data = good_data()
    data["components"][0]["dependencies"] = ["ghost"]
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "ghost" in r.stdout


def test_dangling_flow_step_fails(tmp_path):
    data = good_data()
    data["flows"][0]["steps"][0]["to"] = "ghost"
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "ghost" in r.stdout


def test_duplicate_ids_fail(tmp_path):
    data = good_data()
    data["components"][1]["id"] = "cli"
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "duplicate" in r.stdout.lower()


def test_unknown_layer_fails(tmp_path):
    data = good_data()
    data["components"][0]["layer"] = "nope"
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "nope" in r.stdout


def test_nonexistent_path_fails(tmp_path):
    data = good_data()
    data["components"][0]["path"] = "cli/ghost.py"
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "ghost.py" in r.stdout


def test_dot_path_fails(tmp_path):
    data = good_data()
    data["components"][0]["path"] = "."
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "forbidden path" in r.stdout


def test_parent_traversal_path_fails(tmp_path):
    data = good_data()
    data["components"][0]["path"] = "../outside.py"
    jp = make_repo(tmp_path, data)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "forbidden path" in r.stdout


def test_unclaimed_source_dir_fails_coverage(tmp_path):
    jp = make_repo(tmp_path)
    for extra in ("web", "worker", "jobs"):
        d = tmp_path / extra
        d.mkdir()
        (d / "x.py").write_text("# stub\n")
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "coverage" in r.stdout


def test_non_source_dirs_ignored_by_coverage(tmp_path):
    jp = make_repo(tmp_path)
    for ignored in ("node_modules", "dist", ".hidden"):
        (tmp_path / ignored).mkdir()
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 0, r.stdout


def test_missing_html_fails(tmp_path):
    jp = make_repo(tmp_path)
    (jp.parent / "architecture.html").unlink()
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "html" in r.stdout.lower()


def test_tampered_embedded_json_fails(tmp_path):
    jp = make_repo(tmp_path)
    html = jp.parent / "architecture.html"
    other = good_data()
    other["name"] = "tampered"
    html.write_text(
        '<!doctype html><html><body><script id="archmap-data" '
        'type="application/json">' + json.dumps(other) + "</script></body></html>"
    )
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "differs" in r.stdout


def test_external_resource_in_html_fails(tmp_path):
    jp = make_repo(tmp_path)
    html = jp.parent / "architecture.html"
    html.write_text(html.read_text().replace(
        "<body>", '<body><script src="https://cdn.example.com/x.js"></script>'))
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 1
    assert "external" in r.stdout


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                   env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "HOME": str(root)})


def _git_head(root):
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def make_repo_rewrite(tmp_path, data):
    """Rewrite json+html in an existing fixture tree with new data."""
    out = tmp_path / "docs" / "architecture"
    (out / "architecture.json").write_text(json.dumps(data, indent=2))
    (out / "architecture.html").write_text(
        '<!doctype html><html><body><script id="archmap-data" '
        'type="application/json">' + json.dumps(data) + "</script></body></html>"
    )
    return out / "architecture.json"


def test_matching_head_sha_passes(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    make_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")
    data = good_data()
    data["generated"]["commit_sha"] = _git_head(tmp_path)
    jp = make_repo_rewrite(tmp_path, data)
    r = run_validate(jp, tmp_path)
    assert r.returncode == 0, r.stdout


def test_stale_sha_fails(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    jp = make_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")
    r = run_validate(jp, tmp_path)
    assert r.returncode == 1
    assert "stale" in r.stdout


VIEWER = VALIDATE.parent.parent / "assets" / "viewer.html"
DATA_BLOCK_RE = re.compile(
    r'<script id="archmap-data" type="application/json">(.*?)</script>', re.S
)


def test_viewer_template_has_placeholder_block():
    text = VIEWER.read_text(encoding="utf-8")
    m = DATA_BLOCK_RE.search(text)
    assert m, "viewer.html missing archmap-data block"
    embedded = json.loads(m.group(1))
    assert embedded.get("__placeholder__") is True


def test_viewer_template_no_external_resources():
    stripped = DATA_BLOCK_RE.sub("", VIEWER.read_text(encoding="utf-8"))
    assert not re.search(r'\b(?:src|href)\s*=\s*["\']https?://', stripped)


def test_checks_yaml_goodhart_format():
    text = (VALIDATE.parent.parent / "eval" / "checks.yaml").read_text()
    assert "checks:" in text and "holdout:" in text
    n_check = text.count("- check:")
    assert n_check >= 5
    assert text.count("false_pass:") == n_check
    assert text.count("mitigation:") == n_check


def test_skill_md_restates_validator_thresholds():
    text = (VALIDATE.parent.parent / "SKILL.md").read_text()
    for needle in (">= 5 components", ">= 2 flows", "80%", "rev-parse HEAD",
                   "archmap-data", "commit_sha"):
        assert needle in text, f"SKILL.md missing: {needle}"


def test_injected_viewer_passes_validator(tmp_path):
    data = good_data()
    jp = make_repo(tmp_path, data)
    template = VIEWER.read_text(encoding="utf-8")
    injected = DATA_BLOCK_RE.sub(
        lambda _m: '<script id="archmap-data" type="application/json">'
        + json.dumps(data) + "</script>",
        template,
    )
    (jp.parent / "architecture.html").write_text(injected)
    r = run_validate(jp, tmp_path, "--no-git")
    assert r.returncode == 0, r.stdout

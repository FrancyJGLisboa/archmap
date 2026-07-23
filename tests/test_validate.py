"""Tests for scripts/validate.py — run via: uv run --with pytest pytest tests/ -v"""
import json
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

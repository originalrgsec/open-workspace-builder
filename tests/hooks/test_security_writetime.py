"""OWB-S151: security-writetime hook tests.

Covers the 9 shipped rules (one positive + one false-positive case each
where applicable) plus the suppression-marker path, non-write tool
pass-through, empty-content pass-through, and malformed-JSON
pass-through.

The hook lives at
``src/open_workspace_builder/vendor/ecc/hooks/security-writetime.py``
as a standalone script. Tests load it via ``importlib`` because the
dashed filename cannot be imported as a regular module.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "open_workspace_builder"
    / "vendor"
    / "ecc"
    / "hooks"
    / "security-writetime.py"
)


@pytest.fixture(scope="module")
def hook_module():
    """Load the dashed-filename hook script as an importable module."""
    spec = importlib.util.spec_from_file_location("security_writetime", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["security_writetime"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("security_writetime", None)
        raise
    return mod


# ── Rule-by-rule positive cases ───────────────────────────────────────


def test_gha_workflow_injection_detected(hook_module) -> None:
    yaml_src = (
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo ${{ github.event.issue.title }}\n"
    )
    findings = hook_module.evaluate("/repo/.github/workflows/ci.yml", yaml_src)
    names = [name for name, _ in findings]
    assert "gha-workflow-injection" in names


def test_py_subprocess_shell_true_detected(hook_module) -> None:
    src = 'import subprocess\nsubprocess.run("ls -l", shell=True)\n'
    findings = hook_module.evaluate("scripts/run.py", src)
    assert any(name == "py-subprocess-shell-true" for name, _ in findings)


def test_py_yaml_unsafe_load_detected(hook_module) -> None:
    src = "import yaml\ndata = yaml.load(open('x.yml').read())\n"
    findings = hook_module.evaluate("app/load.py", src)
    assert any(name == "py-yaml-unsafe-load" for name, _ in findings)


def test_py_yaml_safe_loader_not_flagged(hook_module) -> None:
    src = "import yaml\ndata = yaml.load(f, Loader=yaml.SafeLoader)\n"
    findings = hook_module.evaluate("app/load.py", src)
    assert not any(name == "py-yaml-unsafe-load" for name, _ in findings)


def test_py_requests_verify_false_detected(hook_module) -> None:
    src = "import requests\nresp = requests.get('https://x', verify=False)\n"
    findings = hook_module.evaluate("app/client.py", src)
    assert any(name == "py-requests-verify-false" for name, _ in findings)


def test_py_flask_debug_true_detected(hook_module) -> None:
    src = "from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)\n"
    findings = hook_module.evaluate("app/server.py", src)
    assert any(name == "py-flask-debug-true" for name, _ in findings)


def test_py_eval_detected(hook_module) -> None:
    src = "def parse(s):\n    return eval(s)\n"
    findings = hook_module.evaluate("app/parse.py", src)
    assert any(name == "py-eval-exec" for name, _ in findings)


def test_py_pickle_loads_detected(hook_module) -> None:
    src = "import pickle\nobj = pickle.loads(raw)\n"
    findings = hook_module.evaluate("app/deserialize.py", src)
    assert any(name == "py-pickle-loads" for name, _ in findings)


def test_bind_all_interfaces_detected_in_config(hook_module) -> None:
    src = 'host = "0.0.0.0"\nport = 8080\n'
    findings = hook_module.evaluate("deploy/config.toml", src)
    assert any(name == "bind-all-interfaces" for name, _ in findings)


def test_hardcoded_private_key_detected_any_path(hook_module) -> None:
    # gitleaks:allow — synthetic PEM header with a non-key body for rule testing.
    begin = "-----BEGIN " + "RSA PRIVATE KEY-----"
    end = "-----END " + "RSA PRIVATE KEY-----"
    src = f"{begin}\nNOT-A-REAL-KEY\n{end}\n"
    findings = hook_module.evaluate("src/secrets/notes.md", src)
    assert any(name == "hardcoded-private-key" for name, _ in findings)


# ── Suppression marker ─────────────────────────────────────────────────


def test_noqa_marker_suppresses_finding(hook_module) -> None:
    src = "import subprocess\nsubprocess.run(cmd, shell=True)  # noqa: security\n"
    findings = hook_module.evaluate("app/run.py", src)
    assert findings == []


# ── Path-filter boundaries ─────────────────────────────────────────────


def test_python_rule_skipped_for_non_python_path(hook_module) -> None:
    src = "subprocess.run(x, shell=True)\n"
    findings = hook_module.evaluate("README.md", src)
    assert not any(name == "py-subprocess-shell-true" for name, _ in findings)


def test_workflow_rule_skipped_outside_gha_dir(hook_module) -> None:
    yaml_src = "run: echo ${{ github.event.issue.title }}\n"
    findings = hook_module.evaluate("docs/examples.yml", yaml_src)
    assert not any(name == "gha-workflow-injection" for name, _ in findings)


# ── main() tool-name gating ────────────────────────────────────────────


def test_main_skips_non_write_tool(hook_module, monkeypatch) -> None:
    payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x.py"}})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hook_module.main() == 0


def test_main_skips_empty_content(hook_module, monkeypatch) -> None:
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "x.py", "content": ""}})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hook_module.main() == 0


def test_main_handles_malformed_json(hook_module, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("{not valid json"))
    assert hook_module.main() == 0


def test_main_warns_on_write_with_finding(hook_module, monkeypatch, capsys) -> None:
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "app/run.py",
                "content": "import subprocess\nsubprocess.run(cmd, shell=True)\n",
            },
        }
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hook_module.main() == 0
    captured = capsys.readouterr()
    assert "security-writetime" in captured.err
    assert "py-subprocess-shell-true" in captured.err
    assert captured.out == ""

"""OWB-S133: dependency-gate.py argv parser regression tests.

Covers AC-1 through AC-5 and EC-1, EC-2 from the story. The hook lives
at ``src/open_workspace_builder/vendor/ecc/hooks/dependency-gate.py``
(a standalone script, dashed filename). Tests load it via ``importlib``
because the filename can't be imported as a regular module.

Sprint 29 regressions (the inputs that motivated this story):

    uv pip install pytest-cov 2>&1 | tail -3
    uv add --dev pytest-cov

Previous parser returned bogus ``2`` and ``|`` as package names. The
rewritten parser must never emit non-package tokens.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Absolute path to the vendored hook script.
HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "open_workspace_builder"
    / "vendor"
    / "ecc"
    / "hooks"
    / "dependency-gate.py"
)


@pytest.fixture(scope="module")
def hook_module():
    """Load the dashed-filename hook script as an importable module.

    Must register the module in ``sys.modules`` before ``exec_module``
    so that ``@dataclass`` can resolve its own class's ``__module__``
    back to a real module object (dataclasses introspect sys.modules
    to walk the class's annotations).
    """
    spec = importlib.util.spec_from_file_location("dependency_gate", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dependency_gate"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("dependency_gate", None)
        raise
    return mod


def _names(specs) -> list[str]:
    return [s.name for s in specs]


class TestShellOperatorHandling:
    """AC-1: shell operators, redirection, and file descriptors are ignored."""

    def test_pipe_and_stderr_redirect_ignored(self, hook_module) -> None:
        """Sprint 29 regression: `uv pip install pytest-cov 2>&1 | tail -3`."""
        specs = hook_module.extract_packages("uv pip install pytest-cov 2>&1 | tail -3")
        assert _names(specs) == ["pytest-cov"]

    def test_stdout_redirect_ignored(self, hook_module) -> None:
        specs = hook_module.extract_packages("uv pip install pkg > out.log")
        assert _names(specs) == ["pkg"]

    def test_append_redirect_ignored(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install pkg >> log.txt 2>&1")
        assert _names(specs) == ["pkg"]

    def test_logical_operators_terminate_parsing(self, hook_module) -> None:
        """Only packages before && are installed by the install command."""
        specs = hook_module.extract_packages("pip install alpha && echo done")
        assert _names(specs) == ["alpha"]

    def test_semicolon_terminates_parsing(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install alpha ; pip install beta")
        # Both install commands should be recognized.
        assert set(_names(specs)) == {"alpha", "beta"}

    def test_standalone_pipe_token_is_not_a_package(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install pkg | grep foo")
        names = _names(specs)
        assert "|" not in names
        assert "grep" not in names
        assert "foo" not in names
        assert names == ["pkg"]

    def test_numeric_fd_token_is_not_a_package(self, hook_module) -> None:
        """The `2` in `2>&1` must never surface as a package name."""
        specs = hook_module.extract_packages("pip install pkg 2>&1")
        assert _names(specs) == ["pkg"]
        assert "2" not in _names(specs)


class TestFlagHandling:
    """AC-1: flags must be ignored."""

    def test_ignores_dev_flag(self, hook_module) -> None:
        """Sprint 29 regression: `uv add --dev pytest-cov`."""
        specs = hook_module.extract_packages("uv add --dev pytest-cov")
        assert _names(specs) == ["pytest-cov"]

    def test_ignores_upgrade_flag(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install --upgrade pkg")
        assert _names(specs) == ["pkg"]

    def test_ignores_short_flag_with_value(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install -r requirements.txt pkg")
        # -r's value (requirements.txt) is a file path, not a package.
        assert "requirements.txt" not in _names(specs)
        assert "pkg" in _names(specs)


class TestPathHandling:
    """AC-1: editable paths and local paths are not packages."""

    def test_editable_dot(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install -e .")
        assert _names(specs) == []

    def test_editable_relative_path(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install -e ./sibling-project")
        assert _names(specs) == []

    def test_absolute_path(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install /tmp/wheel.whl")
        assert _names(specs) == []


class TestUrlAndGitHandling:
    """AC-1: git+ and URL refs are not queried as PyPI packages."""

    def test_git_url(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install git+https://github.com/org/repo@main")
        assert _names(specs) == []

    def test_https_url(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install https://example.com/pkg-1.0.tar.gz")
        assert _names(specs) == []


class TestVersionPinRespect:
    """AC-2: `==X.Y.Z` pins are extracted into pinned_version."""

    def test_exact_pin_extracted(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install pkg==1.2.3")
        assert len(specs) == 1
        assert specs[0].name == "pkg"
        assert specs[0].pinned_version == "1.2.3"

    def test_exact_pin_with_double_quote(self, hook_module) -> None:
        specs = hook_module.extract_packages('pip install "pkg==2.0.0"')
        assert len(specs) == 1
        assert specs[0].name == "pkg"
        assert specs[0].pinned_version == "2.0.0"

    def test_unpinned_has_none_version(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install pkg")
        assert specs[0].pinned_version is None


class TestVersionRangeFallback:
    """AC-3: range specifiers keep pinned_version=None; no crash."""

    def test_ge_range(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install 'pkg>=1.0,<2.0'")
        assert len(specs) == 1
        assert specs[0].name == "pkg"
        # Conservative: do not claim to know the final version.
        assert specs[0].pinned_version is None

    def test_single_gt(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install pkg>=1.0")
        assert specs[0].name == "pkg"
        assert specs[0].pinned_version is None

    def test_compatible_release(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install 'pkg~=1.2'")
        assert specs[0].name == "pkg"
        assert specs[0].pinned_version is None

    def test_not_equal(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install 'pkg!=1.0'")
        assert specs[0].name == "pkg"
        assert specs[0].pinned_version is None


class TestExtrasHandling:
    """Extras like pkg[extra] should strip cleanly."""

    def test_single_extra(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install 'himitsubako[keychain]'")
        assert specs[0].name == "himitsubako"

    def test_extra_plus_pin(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install 'himitsubako[keychain]>=0.7.0'")
        assert specs[0].name == "himitsubako"
        assert specs[0].pinned_version is None


class TestUvSyncBehavior:
    """AC-4: `uv sync` and `uv lock` are explicitly out of scope."""

    def test_uv_sync_emits_no_packages(self, hook_module) -> None:
        """Documented out of scope: sync moves installed set to the existing
        lock; the lock was gated when packages were added."""
        specs = hook_module.extract_packages("uv sync")
        assert specs == []

    def test_uv_sync_with_extras_flag_still_emits_nothing(self, hook_module) -> None:
        specs = hook_module.extract_packages("uv sync --all-extras")
        assert specs == []

    def test_uv_lock_emits_no_packages(self, hook_module) -> None:
        specs = hook_module.extract_packages("uv lock")
        assert specs == []


class TestMultiplePackages:
    """EC-2: multiple packages each checked."""

    def test_three_packages_one_command(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install alpha beta==1.0 'gamma>=2.0'")
        names = _names(specs)
        assert set(names) == {"alpha", "beta", "gamma"}
        # Exact pin preserved on beta only.
        by_name = {s.name: s for s in specs}
        assert by_name["beta"].pinned_version == "1.0"
        assert by_name["alpha"].pinned_version is None
        assert by_name["gamma"].pinned_version is None


class TestSubstitutionBlocked:
    """EC-1: command substitution cannot be safely parsed → emit nothing."""

    def test_command_substitution_parens(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install $(echo pkg)")
        # Conservative: do not guess. An empty result will hit the
        # "not an install command" path or leave gate decision to the
        # operator; either is safer than treating $(echo as a package.
        assert "$(echo" not in _names(specs)
        assert "pkg)" not in _names(specs)

    def test_backtick_substitution(self, hook_module) -> None:
        specs = hook_module.extract_packages("pip install `echo pkg`")
        # Same: no bogus package names.
        for name in _names(specs):
            assert "`" not in name
            assert "echo" != name


class TestNonInstallCommands:
    """Passes cleanly for commands that are not installs."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "ls -la",
            "git status",
            "pytest tests/",
            "echo hello | wc -l",
            "uv run pytest",
        ],
    )
    def test_no_packages_extracted(self, hook_module, cmd: str) -> None:
        assert hook_module.extract_packages(cmd) == []


class TestSprint29RegressionBundle:
    """AC-5: parametrized suite over every input that broke in Sprint 29."""

    @pytest.mark.parametrize(
        "cmd,expected_names",
        [
            ("uv pip install pytest-cov", ["pytest-cov"]),
            ("uv pip install pytest-cov 2>&1 | tail -3", ["pytest-cov"]),
            ("uv add --dev pytest-cov", ["pytest-cov"]),
            ("uv add pytest-cov", ["pytest-cov"]),
            ("uv pip install pkg==1.2.3", ["pkg"]),
            ("uv pip install 'pkg>=1.0,<2.0'", ["pkg"]),
            ("pip install -e .", []),
            ("pip install git+https://github.com/org/repo@main", []),
            ("pip install --upgrade pkg", ["pkg"]),
        ],
    )
    def test_regression_input(self, hook_module, cmd: str, expected_names) -> None:
        specs = hook_module.extract_packages(cmd)
        assert _names(specs) == expected_names, f"cmd={cmd!r}"

    @pytest.mark.parametrize(
        "cmd",
        [
            "uv pip install pytest-cov 2>&1 | tail -3",
            "uv add --dev pytest-cov",
            "pip install pkg | grep foo",
            "pip install pkg > log.txt 2>&1",
        ],
    )
    def test_no_bogus_tokens_emitted(self, hook_module, cmd: str) -> None:
        names = _names(hook_module.extract_packages(cmd))
        for bogus in ("2", "|", "tail", "grep", "log.txt", ">", ">>", "&&", "2>&1"):
            assert bogus not in names, f"cmd={cmd!r} leaked token {bogus!r}"

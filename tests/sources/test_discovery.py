"""Tests for S035 — Source Discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.sources.discovery import (
    DiscoveredFile,
    SourceConfig,
    SourceDiscovery,
    _is_excluded,
)


@pytest.fixture
def sample_source() -> SourceConfig:
    return SourceConfig(
        name="ecc",
        repo_url="https://github.com/example/ecc",
        pin="abc123",
        patterns=("**/SKILL.md", "**/skills/*/SKILL.md"),
        exclude=("vendor/**", "tests/**"),
    )


@pytest.fixture
def repo_tree(tmp_path: Path) -> Path:
    (tmp_path / "SKILL.md").write_text("# Top Skill")
    skill_a = tmp_path / "agents" / "architect"
    skill_a.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text("# Architect Skill")
    skill_b = tmp_path / "skills" / "code-review"
    skill_b.mkdir(parents=True)
    (skill_b / "SKILL.md").write_text("# Code Review Skill")
    vendor = tmp_path / "vendor" / "external"
    vendor.mkdir(parents=True)
    (vendor / "SKILL.md").write_text("# Vendor Skill (excluded)")
    tests = tmp_path / "tests" / "fixtures"
    tests.mkdir(parents=True)
    (tests / "SKILL.md").write_text("# Test Skill (excluded)")
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "agents" / "architect" / "config.yaml").write_text("key: val")
    return tmp_path


class TestSourceConfig:
    def test_frozen(self) -> None:
        sc = SourceConfig(name="x", repo_url="https://example.com", pin="abc")
        with pytest.raises(AttributeError):
            sc.name = "y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        sc = SourceConfig(name="x", repo_url="https://example.com", pin="abc")
        assert sc.discovery_method == "glob"
        assert sc.patterns == ("**/SKILL.md",)
        assert sc.exclude == ()


class TestDiscoveredFile:
    def test_frozen(self) -> None:
        df = DiscoveredFile(source_name="ecc", relative_path="a.md", absolute_path="/a.md")
        with pytest.raises(AttributeError):
            df.relative_path = "b.md"  # type: ignore[misc]

    def test_fields(self) -> None:
        df = DiscoveredFile(source_name="ecc", relative_path="a/b.md", absolute_path="/x/a/b.md")
        assert df.source_name == "ecc"
        assert df.relative_path == "a/b.md"
        assert df.absolute_path == "/x/a/b.md"


class TestIsExcluded:
    def test_simple_glob(self) -> None:
        assert _is_excluded("vendor/foo/SKILL.md", ("vendor/**",)) is True

    def test_no_match(self) -> None:
        assert _is_excluded("agents/architect/SKILL.md", ("vendor/**",)) is False

    def test_tests_excluded(self) -> None:
        assert _is_excluded("tests/fixtures/SKILL.md", ("tests/**",)) is True

    def test_empty_excludes(self) -> None:
        assert _is_excluded("anything/SKILL.md", ()) is False

    def test_multiple_patterns(self) -> None:
        assert _is_excluded("vendor/x.md", ("tests/**", "vendor/**")) is True
        assert _is_excluded("tests/x.md", ("tests/**", "vendor/**")) is True
        assert _is_excluded("agents/x.md", ("tests/**", "vendor/**")) is False


class TestSourceDiscovery:
    def test_discover_glob_matching(self, sample_source: SourceConfig, repo_tree: Path) -> None:
        discovery = SourceDiscovery([sample_source])
        files = discovery.discover("ecc", str(repo_tree))
        rel_paths = {f.relative_path for f in files}
        assert "SKILL.md" in rel_paths
        assert "agents/architect/SKILL.md" in rel_paths
        assert "skills/code-review/SKILL.md" in rel_paths

    def test_exclude_patterns(self, sample_source: SourceConfig, repo_tree: Path) -> None:
        discovery = SourceDiscovery([sample_source])
        files = discovery.discover("ecc", str(repo_tree))
        rel_paths = {f.relative_path for f in files}
        assert "vendor/external/SKILL.md" not in rel_paths
        assert "tests/fixtures/SKILL.md" not in rel_paths

    def test_non_matching_files_ignored(self, sample_source: SourceConfig, repo_tree: Path) -> None:
        discovery = SourceDiscovery([sample_source])
        files = discovery.discover("ecc", str(repo_tree))
        rel_paths = {f.relative_path for f in files}
        assert "README.md" not in rel_paths
        assert "agents/architect/config.yaml" not in rel_paths

    def test_unknown_source_raises(self, sample_source: SourceConfig) -> None:
        discovery = SourceDiscovery([sample_source])
        with pytest.raises(KeyError, match="Unknown source"):
            discovery.discover("nonexistent", "/tmp")

    def test_nonexistent_path_raises(self, sample_source: SourceConfig) -> None:
        discovery = SourceDiscovery([sample_source])
        with pytest.raises(FileNotFoundError):
            discovery.discover("ecc", "/nonexistent/path/xyz")

    def test_empty_repo(self, sample_source: SourceConfig, tmp_path: Path) -> None:
        discovery = SourceDiscovery([sample_source])
        files = discovery.discover("ecc", str(tmp_path))
        assert files == []

    def test_multiple_sources(self, repo_tree: Path) -> None:
        src_a = SourceConfig(name="a", repo_url="https://a.com", pin="1", patterns=("**/SKILL.md",))
        src_b = SourceConfig(name="b", repo_url="https://b.com", pin="2", patterns=("**/*.yaml",))
        discovery = SourceDiscovery([src_a, src_b])
        files_a = discovery.discover("a", str(repo_tree))
        files_b = discovery.discover("b", str(repo_tree))
        assert all(f.source_name == "a" for f in files_a)
        assert all(f.source_name == "b" for f in files_b)
        assert any(f.relative_path.endswith(".yaml") for f in files_b)

    def test_source_names_property(self) -> None:
        sources = [
            SourceConfig(name="a", repo_url="", pin=""),
            SourceConfig(name="b", repo_url="", pin=""),
        ]
        discovery = SourceDiscovery(sources)
        assert set(discovery.source_names) == {"a", "b"}

    def test_get_config(self, sample_source: SourceConfig) -> None:
        discovery = SourceDiscovery([sample_source])
        config = discovery.get_config("ecc")
        assert config.repo_url == "https://github.com/example/ecc"

    def test_get_config_missing_raises(self, sample_source: SourceConfig) -> None:
        discovery = SourceDiscovery([sample_source])
        with pytest.raises(KeyError):
            discovery.get_config("missing")

    def test_discovered_files_sorted(self, sample_source: SourceConfig, repo_tree: Path) -> None:
        discovery = SourceDiscovery([sample_source])
        files = discovery.discover("ecc", str(repo_tree))
        rel_paths = [f.relative_path for f in files]
        assert rel_paths == sorted(rel_paths)

    def test_absolute_paths_valid(self, sample_source: SourceConfig, repo_tree: Path) -> None:
        discovery = SourceDiscovery([sample_source])
        files = discovery.discover("ecc", str(repo_tree))
        for f in files:
            assert Path(f.absolute_path).exists()

    def test_directories_not_included(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").mkdir()
        source = SourceConfig(name="x", repo_url="", pin="", patterns=("**/SKILL.md",))
        discovery = SourceDiscovery([source])
        files = discovery.discover("x", str(tmp_path))
        assert files == []


class TestSourcesConfigLoading:
    def test_load_sources_from_yaml(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "sources:\n"
            "  ecc:\n"
            '    repo_url: "https://github.com/example/ecc"\n'
            '    pin: "abc123"\n'
            "    patterns:\n"
            '      - "**/SKILL.md"\n'
            '      - "**/skills/*/SKILL.md"\n'
            "    exclude:\n"
            '      - "vendor/**"\n',
            encoding="utf-8",
        )
        config = load_config(config_file, cli_name="owb")
        assert "ecc" in config.sources.entries
        entry = config.sources.entries["ecc"]
        assert entry.repo_url == "https://github.com/example/ecc"
        assert entry.pin == "abc123"
        assert entry.patterns == ("**/SKILL.md", "**/skills/*/SKILL.md")
        assert entry.exclude == ("vendor/**",)

    def test_default_sources_empty(self) -> None:
        from open_workspace_builder.config import Config

        config = Config()
        assert config.sources.entries == {}

    def test_multiple_sources_yaml(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "sources:\n"
            "  ecc:\n"
            '    repo_url: "https://github.com/example/ecc"\n'
            '    pin: "abc"\n'
            "  custom:\n"
            '    repo_url: "https://github.com/example/custom"\n'
            '    pin: "def"\n'
            '    discovery_method: "custom"\n',
            encoding="utf-8",
        )
        config = load_config(config_file, cli_name="owb")
        assert len(config.sources.entries) == 2
        assert config.sources.entries["custom"].discovery_method == "custom"

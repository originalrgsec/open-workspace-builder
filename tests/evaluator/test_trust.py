"""Tests for trust tier assignment (S029)."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.evaluator.trust import (
    TrustTierAssigner,
    TrustTierResult,
    _matches_source_prefix,
)
from open_workspace_builder.registry.registry import Registry

_POLICY_YAML = """\
id: "owb-default"
version: "1.0.0"
type: "trust_policy"
author: "Test"
description: "Test trust policy"
compatibility: ">=0.1.0"

payload:
  tiers:
    - level: 0
      name: "T0"
      description: "Owner-authored"
      criteria:
        source_prefixes:
          - "content/custom/"
          - "content/skills/"
        requires_security_scan: false
        requires_evaluation: false
        requires_owner_approval: false
      actions:
        auto_install: true
        requires_review: false
        quarantine: false
    - level: 1
      name: "T1"
      description: "Verified"
      criteria:
        source_prefixes: []
        requires_security_scan: true
        requires_evaluation: true
        requires_owner_approval: true
      actions:
        auto_install: false
        requires_review: true
        quarantine: false
    - level: 2
      name: "T2"
      description: "Unverified"
      criteria:
        source_prefixes: []
        requires_security_scan: false
        requires_evaluation: false
        requires_owner_approval: false
      actions:
        auto_install: false
        requires_review: true
        quarantine: true
"""


def _make_registry(tmp_path: Path) -> Registry:
    d = tmp_path / "policies"
    d.mkdir(exist_ok=True)
    (d / "owb-default.yaml").write_text(_POLICY_YAML, encoding="utf-8")
    return Registry(base_dirs=[d])


class TestMatchesSourcePrefix:
    def test_matches_content_custom(self) -> None:
        assert _matches_source_prefix("content/custom/my-skill.md", ["content/custom/"])

    def test_matches_content_skills(self) -> None:
        assert _matches_source_prefix("content/skills/audit/main.md", ["content/skills/"])

    def test_no_match(self) -> None:
        assert not _matches_source_prefix("vendor/ecc/agents/foo.md", ["content/custom/"])

    def test_backslash_normalization(self) -> None:
        assert _matches_source_prefix("content\\custom\\skill.md", ["content/custom/"])

    def test_empty_prefixes(self) -> None:
        assert not _matches_source_prefix("anything", [])


class TestTrustTierAssigner:
    def test_tier_0_owner_authored(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(content_path="content/custom/my-skill.md", source=None)
        assert result.tier == 0
        assert result.criteria_met["source_prefix_match"] is True

    def test_tier_0_skills_path(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(content_path="content/skills/vault-audit/main.md", source=None)
        assert result.tier == 0

    def test_tier_0_rejected_with_upstream(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(
            content_path="content/custom/my-skill.md",
            source="https://github.com/upstream/repo",
        )
        assert result.tier != 0

    def test_tier_1_all_checks_passed(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(
            content_path="vendor/ecc/agents/code-reviewer.md",
            source="https://github.com/ecc/repo",
            security_passed=True,
            evaluation_passed=True,
            owner_approved=True,
        )
        assert result.tier == 1

    def test_tier_2_missing_security(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(
            content_path="vendor/ecc/agents/foo.md",
            security_passed=False,
            evaluation_passed=True,
            owner_approved=True,
        )
        assert result.tier == 2
        assert "security scan" in result.reasoning

    def test_tier_2_missing_evaluation(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(
            content_path="vendor/ecc/agents/foo.md",
            security_passed=True,
            evaluation_passed=False,
            owner_approved=True,
        )
        assert result.tier == 2
        assert "evaluation" in result.reasoning

    def test_tier_2_missing_approval(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(
            content_path="vendor/ecc/agents/foo.md",
            security_passed=True,
            evaluation_passed=True,
            owner_approved=False,
        )
        assert result.tier == 2
        assert "owner approval" in result.reasoning

    def test_tier_2_all_missing(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        result = assigner.assign(content_path="vendor/ecc/agents/foo.md", source="upstream")
        assert result.tier == 2

    def test_transition_2_to_1(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        r1 = assigner.assign(content_path="vendor/agents/foo.md", source="upstream")
        assert r1.tier == 2
        r2 = assigner.assign(
            content_path="vendor/agents/foo.md",
            source="upstream",
            security_passed=True,
            evaluation_passed=True,
            owner_approved=True,
        )
        assert r2.tier == 1

    def test_regression_1_to_2(self, tmp_path: Path) -> None:
        assigner = TrustTierAssigner(registry=_make_registry(tmp_path))
        r1 = assigner.assign(
            content_path="vendor/agents/foo.md",
            source="upstream",
            security_passed=True,
            evaluation_passed=True,
            owner_approved=True,
        )
        assert r1.tier == 1
        r2 = assigner.assign(
            content_path="vendor/agents/foo.md",
            source="upstream",
            security_passed=False,
            evaluation_passed=True,
            owner_approved=True,
        )
        assert r2.tier == 2

    def test_result_is_frozen(self) -> None:
        result = TrustTierResult(tier=0, reasoning="test", criteria_met={})
        with pytest.raises(AttributeError):
            result.tier = 1  # type: ignore[misc]


class TestTrustTierAssignerErrors:
    def test_missing_policy_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            TrustTierAssigner(registry=Registry(base_dirs=[tmp_path]), policy_name="nonexistent")

    def test_wrong_type_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "p"
        d.mkdir()
        (d / "bad.yaml").write_text(
            'id: "bad"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  x: 1\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="expected 'trust_policy'"):
            TrustTierAssigner(registry=Registry(base_dirs=[d]), policy_name="bad")

    def test_no_tiers_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "p"
        d.mkdir()
        (d / "empty.yaml").write_text(
            'id: "empty"\nversion: "1.0.0"\ntype: "trust_policy"\npayload:\n  tiers: []\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="no tiers"):
            TrustTierAssigner(registry=Registry(base_dirs=[d]), policy_name="empty")


class TestBundledTrustPolicy:
    def test_bundled_policy_loads(self) -> None:
        policy_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "open_workspace_builder"
            / "evaluator"
            / "data"
            / "trust_policies"
        )
        registry = Registry(base_dirs=[policy_dir])
        assigner = TrustTierAssigner(registry=registry)
        result = assigner.assign(content_path="content/custom/my-skill.md", source=None)
        assert result.tier == 0

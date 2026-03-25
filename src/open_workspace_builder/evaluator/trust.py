"""Trust tier assignment using registry-loaded policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_workspace_builder.registry.registry import Registry


@dataclass(frozen=True)
class TrustTierResult:
    """Result of assigning a trust tier to content."""

    tier: int
    reasoning: str
    criteria_met: dict[str, bool]


def _load_policy(registry: Registry, policy_name: str) -> dict[str, Any]:
    """Load a trust policy from the registry by name.

    Raises ValueError if the policy is not found or has no tiers.
    """
    item = registry.get_item(policy_name)
    if item is None:
        raise ValueError(f"Trust policy '{policy_name}' not found in registry")
    if item.type != "trust_policy":
        raise ValueError(
            f"Registry item '{policy_name}' has type '{item.type}', expected 'trust_policy'"
        )
    tiers = item.payload.get("tiers")
    if not tiers:
        raise ValueError(f"Trust policy '{policy_name}' has no tiers defined")
    return item.payload


def _matches_source_prefix(content_path: str, prefixes: list[str]) -> bool:
    """Check if content_path starts with any of the given prefixes."""
    normalized = content_path.replace("\\", "/")
    return any(normalized.startswith(p) for p in prefixes)


class TrustTierAssigner:
    """Assigns trust tiers using registry-loaded policy definitions."""

    def __init__(
        self,
        registry: Registry,
        policy_name: str = "owb-default",
    ) -> None:
        self._policy = _load_policy(registry, policy_name)
        self._tiers = self._policy["tiers"]

    def assign(
        self,
        content_path: str,
        source: str | None = None,
        security_passed: bool = False,
        evaluation_passed: bool = False,
        owner_approved: bool = False,
        sca_critical: bool = False,
        sast_error: bool = False,
    ) -> TrustTierResult:
        """Assign a trust tier based on content path, source, and verification status.

        Classification rules are data-driven from the registry policy YAML:
        Tier 0: Owner-authored content matching source_prefixes with no upstream.
        Tier 1: Passed security + evaluation + owner approval.
        Tier 2: Default for unverified content.

        SCA/SAST overrides:
        - ``sca_critical=True``: blocks Tier 0 assignment, forces manual review.
        - ``sast_error=True``: blocks Tier 0, reduces to Tier 1 at best.
        """
        criteria = {
            "source_prefix_match": False,
            "has_upstream": source is not None,
            "security_passed": security_passed,
            "evaluation_passed": evaluation_passed,
            "owner_approved": owner_approved,
            "sca_clean": not sca_critical,
            "sast_clean": not sast_error,
        }

        has_sca_sast_block = sca_critical or sast_error

        tier_0 = self._get_tier(0)
        if tier_0 is not None and not has_sca_sast_block:
            t0_criteria = tier_0.get("criteria", {})
            prefixes = t0_criteria.get("source_prefixes", [])
            if prefixes and _matches_source_prefix(content_path, prefixes) and source is None:
                criteria["source_prefix_match"] = True
                return TrustTierResult(
                    tier=0,
                    reasoning=(
                        f"Content path '{content_path}' matches Tier 0 source prefix "
                        f"and has no upstream source."
                    ),
                    criteria_met=criteria,
                )

        if has_sca_sast_block:
            blockers: list[str] = []
            if sca_critical:
                blockers.append("critical SCA finding")
            if sast_error:
                blockers.append("SAST error-level finding")
            return TrustTierResult(
                tier=2,
                reasoning=(
                    f"Blocked by supply-chain/SAST findings: {', '.join(blockers)}. "
                    f"Manual review required."
                ),
                criteria_met=criteria,
            )

        if security_passed and evaluation_passed and owner_approved:
            return TrustTierResult(
                tier=1,
                reasoning=(
                    "All verification criteria met: security scan, evaluation, and owner approval."
                ),
                criteria_met=criteria,
            )

        missing: list[str] = []
        if not security_passed:
            missing.append("security scan")
        if not evaluation_passed:
            missing.append("evaluation")
        if not owner_approved:
            missing.append("owner approval")

        return TrustTierResult(
            tier=2,
            reasoning=f"Missing verification: {', '.join(missing)}.",
            criteria_met=criteria,
        )

    def _get_tier(self, level: int) -> dict[str, Any] | None:
        """Get tier definition by level number."""
        for tier in self._tiers:
            if tier.get("level") == level:
                return tier
        return None

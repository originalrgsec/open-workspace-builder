"""OWB-S144 — Wrapper dataclass for CycloneDX Bom + OWB metadata.

Replaces an earlier pattern of monkey-patching ``_owb_options`` and
``_owb_non_allowed_count`` onto the third-party
``cyclonedx.model.bom.Bom`` instance. That pattern leaked abstraction
(OWB depended on the ability to add attributes to a vendored class,
fragile across CycloneDX upgrades) and dominated the pyright basic
error budget (60 of 96 errors came from the ``# type: ignore`` lines
in ``sbom/builder.py``). The wrapper keeps OWB-specific state
adjacent to the ``Bom`` without touching it.

The wrapper is internal to the sbom package. Its attributes are
accessed by name (``wrapped.bom``, ``wrapped.options``,
``wrapped.non_allowed_count``) — no ``__getattr__`` shortcuts, no
attribute-tunnelling to the underlying ``Bom``. Callers that need the
bare ``Bom`` for serialization use ``wrapped.bom`` explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cyclonedx.model.bom import Bom

    from open_workspace_builder.sbom.builder import BomOptions


@dataclass(frozen=True)
class BomWithMetadata:
    """CycloneDX Bom paired with OWB build-time metadata.

    Attributes:
        bom: The underlying :class:`cyclonedx.model.bom.Bom`.
        options: Deterministic overrides the caller passed to
            ``build_bom`` (serial, timestamp). ``None`` when the caller
            did not override.
        non_allowed_count: Number of components whose declared license
            is unknown or outside the allowed-licenses policy. Used
            by the CLI to pick exit code 2 (warnings) vs 0 (clean).
    """

    bom: "Bom"
    options: "BomOptions | None"
    non_allowed_count: int

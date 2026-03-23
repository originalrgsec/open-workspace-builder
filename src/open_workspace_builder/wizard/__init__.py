"""Interactive setup wizard for owb/cwb workspace configuration."""

from open_workspace_builder.wizard.setup import run_setup_wizard
from open_workspace_builder.wizard.vault_scan import scan_vault

__all__ = ["run_setup_wizard", "scan_vault"]

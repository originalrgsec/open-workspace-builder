# Installation

## Prerequisites

Open Workspace Builder requires Python 3.10 or later. You will also need pip (or pipx for isolated installations), Git to clone the repository, and optionally an Obsidian vault for vault analysis features.

## Installation

Install from PyPI:

```bash
pip install open-workspace-builder
```

Or install directly from GitHub for the latest development version:

```bash
pip install git+https://github.com/originalrgsec/open-workspace-builder.git
```

### Optional Extras

```bash
pip install "open-workspace-builder[llm]"     # Layer 3 semantic scanner
pip install "open-workspace-builder[sheets]"  # Google Sheets token export
pip install "open-workspace-builder[xlsx]"    # Excel token export
pip install "open-workspace-builder[mcp]"     # MCP server
```

## Development Installation

Clone the repository and install in development mode with all optional dependencies:

```bash
git clone https://github.com/originalrgsec/open-workspace-builder.git
cd open-workspace-builder
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev,security]"
```

## Verify Installation

Confirm the installation was successful:

```bash
owb --version
owb --help
```

## Next Steps

See the [first-run guide](../howto-first-run.md) for a step-by-step walkthrough of running OWB against your workspace.

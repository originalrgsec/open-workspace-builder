# Configuration

OWB uses a three-layer configuration system. Any setting you omit falls back to the layer below.

## Layer Priority

1. **CLI flags** (highest priority): Override any config value from the command line.
2. **User config file**: `~/.owb/config.yaml` (auto-detected) or any path via `--config`.
3. **Built-in defaults** (lowest priority): Sensible values that work out of the box.

The setup wizard (`owb init` on first run) generates `~/.owb/config.yaml` interactively. Subsequent runs load it automatically.

## Config Sections

| Section | Controls |
|---------|----------|
| `vault` | Obsidian vault name, parent directory, assistant name, template selection |
| `ecc` | ECC catalog enabled/disabled, target directory, agent/command/rule lists |
| `skills` | Which custom skills to install |
| `agent_config` | Workspace config file directory and filename |
| `models` | Per-operation LLM model strings (LiteLLM provider/model format) |
| `security` | Active pattern sets, scanner layer selection |
| `trust` | Trust tier policy selection |
| `marketplace` | Output format (generic, anthropic, openai) |
| `secrets` | Secrets backend selection (env, keyring, age, bitwarden, onepassword) |
| `tokens` | Token tracking: ledger path, budget threshold, auto-record |
| `paths` | Config, data, and credentials directory paths |
| `context_templates` | Whether to deploy personal context files |

## Name-Aware Resolution

OWB resolves configuration paths from the binary name at runtime. When invoked as `owb`, it reads from `~/.owb/config.yaml`. When invoked as `mwb` (or any other downstream wrapper), it reads from `~/.mwb/config.yaml`. This enables vendor-specific packages to share OWB's engine while maintaining separate configuration namespaces.

The `claude_md` YAML key is accepted as a backward-compatible alias for `agent_config`.

## Model Configuration

Models are specified using LiteLLM's `provider/model` format, which means OWB works with any LLM provider:

```yaml
models:
  default: anthropic/claude-sonnet-4-20250514
  security_scan: anthropic/claude-haiku-4-20250514
  eval: anthropic/claude-sonnet-4-20250514
```

Supported providers include Anthropic, OpenAI, Ollama, Azure, AWS Bedrock, and any other provider supported by LiteLLM.

## Token Tracking Configuration

The `tokens` section controls the cost tracking and budget alert system:

```yaml
tokens:
  ledger_path: ""              # default: ~/.owb/data/ledger.jsonl
  budget_threshold: 200.0      # monthly budget in dollars (0 = disabled)
  auto_record: false           # enable session-end hook recording
```

### Custom Model Pricing

Override API-equivalent pricing for models not in the built-in registry by creating `~/.owb/pricing.yaml`:

```yaml
my-custom-model:
  input_per_mtok: 3.0
  output_per_mtok: 15.0
  cache_write_per_mtok: 3.75
  cache_read_per_mtok: 0.30
```

### Google Sheets Export Setup

To export token data to Google Sheets:

1. Install the Sheets extra: `pip install "open-workspace-builder[sheets]"`
2. Store your Google OAuth client credentials: `owb auth google-store --client-id YOUR_ID --client-secret YOUR_SECRET`
3. Run the OAuth flow: `owb auth google`
4. Export: `owb metrics export --format gsheets --sheet-id YOUR_SHEET_ID`

Credentials are encrypted using the configured secrets backend (age, keyring, or env).

## Optional Dependency Groups

| Extra | Provides | Install |
|-------|----------|---------|
| `[sheets]` | Google Sheets export for token tracking | `pip install "open-workspace-builder[sheets]"` |
| `[xlsx]` | Excel export for token tracking | `pip install "open-workspace-builder[xlsx]"` |
| `[llm]` | Layer 3 semantic scanner | `pip install "open-workspace-builder[llm]"` |
| `[mcp]` | MCP server for AI desktop clients | `pip install "open-workspace-builder[mcp]"` |
| `[dev]` | Development dependencies (pytest, ruff) | `pip install "open-workspace-builder[dev]"` |

## Example Config

See [`config.example.yaml`](https://github.com/originalrgsec/open-workspace-builder/blob/main/config.example.yaml) in the repository root for the full schema with inline comments documenting every key.

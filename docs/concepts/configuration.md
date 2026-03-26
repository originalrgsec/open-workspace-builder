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
| `paths` | Config, data, and credentials directory paths |
| `context_templates` | Whether to deploy personal context files |

## Name-Aware Resolution

OWB resolves configuration paths from the binary name at runtime. When invoked as `owb`, it reads from `~/.owb/config.yaml`. When invoked as `cwb` (or any other downstream wrapper), it reads from `~/.cwb/config.yaml`. This enables vendor-specific packages to share OWB's engine while maintaining separate configuration namespaces.

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

## Example Config

See [`config.example.yaml`](https://github.com/VolcanixLLC/open-workspace-builder/blob/main/config.example.yaml) in the repository root for the full schema with inline comments documenting every key.

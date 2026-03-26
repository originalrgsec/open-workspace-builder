# First Run: Starting Fresh

This guide walks through setting up OWB from scratch when you have no existing Obsidian vault. By the end you will have a fully scaffolded workspace, Obsidian connected to it, and the Obsidian MCP server running so your AI agent can read and write vault notes directly.

## Prerequisites

**OWB is installed and on PATH.**

```bash
owb --version
```

If not installed yet, see [Installation](install.md).

**(Optional) An LLM API key is available.** Layer 3 semantic scanning requires a model backend. For a first run, Layers 1 and 2 are sufficient and require no API key.

## Step 1: Run the Setup Wizard

The wizard walks you through model provider selection, secrets backend, vault tiers, and marketplace format.

```bash
owb setup
```

This creates a config file at `~/.owb/config.yaml` with your choices. You can edit it later or re-run the wizard to change settings.

## Step 2: Choose a Workspace Location

Pick a directory that will serve as the root of your AI workspace. All your code projects should live under this directory so the AI agent can discover the workspace configuration by traversing upward.

```bash
WORKSPACE="$HOME/workspace"
mkdir -p "$WORKSPACE"
```

A typical layout after the build:

```
~/workspace/                      <-- workspace root
├── .ai/                          <-- agent config (WORKSPACE.md)
│   └── WORKSPACE.md
├── .skills/                      <-- installed skills
│   └── skills/
├── Obsidian/                     <-- knowledge vault
│   ├── _bootstrap.md
│   ├── _templates/
│   ├── projects/
│   ├── research/
│   ├── decisions/
│   └── ...
├── about-me.md                   <-- context files
├── brand-voice.md
├── working-style.md
├── code-project-a/               <-- your code projects go here
└── code-project-b/
```

If you plan to use ECC (Everything Code Catalog), enable it in your config first:

```bash
# Edit ~/.owb/config.yaml and set:
#   ecc:
#     enabled: true
#     target_dir: ".claude"
```

## Step 3: Build the Workspace

Preview what OWB will create, then build it.

```bash
owb init -t "$WORKSPACE" --dry-run    # preview — nothing written
owb init -t "$WORKSPACE"              # build for real
```

Verify the output:

```bash
ls "$WORKSPACE/Obsidian/"             # vault directories
ls "$WORKSPACE/Obsidian/_templates/"  # note templates
cat "$WORKSPACE/Obsidian/_bootstrap.md" | head -20
```

You should see the vault scaffold with directories for projects, research, decisions, business, and a set of note templates.

## Step 4: Install and Configure Obsidian

If you do not have Obsidian installed yet, download it from [obsidian.md](https://obsidian.md/) and install it.

### Open the vault

1. Launch Obsidian
2. Click **Open folder as vault**
3. Navigate to and select the `Obsidian/` directory inside your workspace (e.g., `~/workspace/Obsidian/`)
4. Obsidian will open the vault and index all the scaffolded files

### Install required community plugins

OWB's vault works best with two community plugins that enable Git sync and the MCP server integration.

1. In Obsidian, go to **Settings > Community plugins**
2. Click **Browse** and search for each plugin below
3. Install and enable each one

**Obsidian Git** (by Vinzent):

- Provides automatic Git backup and sync for the vault
- After installing, go to **Settings > Obsidian Git** and configure:
    - **Auto backup interval:** 10 minutes (or your preference)
    - **Auto pull interval:** 10 minutes
    - **Commit message:** `vault: auto-backup {{date}}`
- Initialize the vault as a Git repo if you have not already:

```bash
cd "$WORKSPACE/Obsidian"
git init
git add -A
git commit -m "vault: initial scaffold from owb init"
```

**Local REST API** (by Adam Coddington):

- Exposes the vault over a local HTTP API that the Obsidian MCP server uses
- After installing, go to **Settings > Local REST API** and note:
    - **Port:** 27124 (default)
    - **API key:** generated automatically — copy this value, you will need it for the MCP server config
    - **Enable non-encrypted (HTTP) server:** enable this for local-only use

Restart Obsidian after enabling both plugins.

## Step 5: Set Up the Obsidian MCP Server

The Obsidian MCP server lets your AI agent read, search, create, and edit vault notes directly through the Model Context Protocol.

### Install the server

```bash
npx obsidian-mcp
```

Or install it globally:

```bash
npm install -g obsidian-mcp
```

### Configure your AI agent to use it

Add the Obsidian MCP server to your agent's MCP configuration. The location depends on your setup:

**For Claude Code** (`~/.claude/settings.json` or project-level `.claude/settings.json`):

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "npx",
      "args": ["obsidian-mcp"],
      "env": {
        "OBSIDIAN_API_KEY": "<your-api-key-from-local-rest-api>",
        "OBSIDIAN_API_URL": "http://localhost:27124"
      }
    }
  }
}
```

**For other MCP-compatible agents**, consult your agent's documentation for MCP server configuration. The server expects two environment variables:

- `OBSIDIAN_API_KEY` — the API key from the Local REST API plugin
- `OBSIDIAN_API_URL` — typically `http://localhost:27124`

### Verify the connection

Start a new AI agent session and ask it to read a vault file:

```
Read _bootstrap.md from the Obsidian vault
```

The agent should be able to retrieve the bootstrap file content through the MCP server. If it cannot connect, verify that Obsidian is running, the Local REST API plugin is enabled, and the API key matches.

## Step 6: Fill In Your Context Files

OWB deployed three context file stubs that the AI agent reads at session start. Fill these in so the agent can calibrate its behavior to your preferences.

```bash
# Check which files need filling
ls "$WORKSPACE/about-me.md" "$WORKSPACE/brand-voice.md" "$WORKSPACE/working-style.md"
```

Open each file and replace the placeholder text with your actual information:

- **about-me.md** — your professional background, domain expertise, and project context
- **brand-voice.md** — writing tone, vocabulary preferences, and register levels
- **working-style.md** — behavioral preferences, output calibration, and decision authority

You can fill these in manually or start an AI session and let the agent guide you through it. The agent config file includes a "First Session Tasks" section that triggers this guided flow automatically.

## Step 7: Verify Everything Works

Start a fresh AI session from the workspace root:

```bash
cd "$WORKSPACE"
claude   # or your preferred AI coding tool
```

In the session, verify:

- The agent reads the bootstrap file and knows the vault structure
- The agent can create and read notes through the Obsidian MCP server
- Context files are loaded (ask the agent to summarize your about-me.md)
- If ECC is enabled, commands appear in `/` autocomplete and agents are available

## Next Steps

- **Add a project:** Create a project folder under `Obsidian/projects/<tier>/` using the project-index template
- **Process research:** Drop notes into `Obsidian/research/inbox/` and use the mobile-inbox-triage skill to process them
- **Keep current:** Run `owb diff` periodically to check for template drift, and `owb migrate` to apply updates
- **Upgrade OWB:** See the [Upgrade Guide](../howto-upgrade.md) when a new version is available

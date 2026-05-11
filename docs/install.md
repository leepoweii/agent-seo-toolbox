# Installation

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- A DataForSEO account ([sign up](https://dataforseo.com/))
- Access to a Neon Postgres database (shared team cache, or your own)

## Install

```bash
uv tool install git+https://github.com/leepoweii/agent-seo-toolbox
```

After install, `seo` is on your PATH:

```bash
seo --version
```

## Configure

### 1. Domain config (interactive)

```bash
seo init
```

Walks you through `own_domain` and `competitor_domains`, writes to `~/.config/agent-seo-toolbox/config.toml`.

### 2. Credentials (manual edit — do NOT paste in chat)

```bash
mkdir -p ~/.config/agent-seo-toolbox
cat > ~/.config/agent-seo-toolbox/.env <<EOF
DATABASE_URL=postgresql://...your-neon-url...
DATAFORSEO_LOGIN=user@example.com
DATAFORSEO_PASSWORD=...
EOF
chmod 600 ~/.config/agent-seo-toolbox/.env
```

### 3. Verify

```bash
seo init --check
```

Expected output:

```json
{"config_valid": true, "db_reachable": true, "dataforseo_auth": "ok"}
```

## Per-project overrides (optional)

You can keep a project-local `agent-seo-toolbox.toml` in any directory to override `own_domain` / `competitors` for that working directory. Useful when handling multiple clients (planned for post-MVP — see `docs/superpowers/specs/2026-04-25-agent-seo-toolbox-design.md`).

## Upgrade

```bash
uv tool upgrade agent-seo-toolbox
```

## Develop locally

```bash
git clone https://github.com/leepoweii/agent-seo-toolbox
cd agent-seo-toolbox
uv sync --extra dev
uv run pytest tests/unit/
```

For integration tests, copy a Neon test branch DATABASE_URL into `.env.test` (gitignored).

# agent-seo-toolbox

A CLI for Taiwan-market SEO ranking and keyword clustering, designed to be invoked by [Claude Code](https://claude.com/claude-code). Wraps DataForSEO + a shared Neon Postgres cache.

---

## Quickstart for new collaborators

If a teammate has shared their `.env` with you, this is the fastest path:

```bash
# 1. Clone + install
git clone https://github.com/leepoweii/agent-seo-toolbox
cd agent-seo-toolbox
uv sync --extra dev

# 2. Drop in the shared secrets (paste from teammate)
mkdir -p ~/.config/agent-seo-toolbox
$EDITOR ~/.config/agent-seo-toolbox/.env
chmod 600 ~/.config/agent-seo-toolbox/.env

# 3. Set your own domain config (interactive)
uv run seo init

# 4. Verify everything connects
uv run seo init --check
# expect: {"config_valid": true, "db_reachable": true, "dataforseo_auth": "ok"}

# 5. Smoke test
echo -e "keyword,volume\n本地 SEO 優化,1200" > /tmp/kw.csv
uv run seo cluster /tmp/kw.csv     # opens browser UI
```

The `.env` you receive contains `DATABASE_URL`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` — **never commit it**. The repo's `.gitignore` already excludes it.

If your Claude Code is set up, just say `/agent-seo-toolbox-init` (or "set up the SEO toolbox") and the init skill will walk you through it after you've placed the `.env`.

---

## Usage

- **For Claude / agents:** see [CLAUDE.md](CLAUDE.md) — auto-loaded by Claude Code, contains the full command reference, error codes, and command patterns.
- **For humans:** see [docs/install.md](docs/install.md) for full install / upgrade / project-override details.

## What you get

- `seo rank-check "<keyword>" "<target_url>"` — find a URL's rank across organic / AI Overview / Featured Snippet
- `seo cluster keywords.csv` — interactive browser UI to group keywords by SERP overlap (drag-drop, threshold slider, AI Overview / PAA preview)
- `seo init` / `seo init --check` — config + connectivity validation

## Methodology

See [docs/methodology.md](docs/methodology.md) for the academic + industry foundations of SERP-overlap clustering (Zhang SIGIR '11, Keyword Insights / SE Ranking conventions).

## License

MIT

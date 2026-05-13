# agent-seo-toolbox — Claude Code Reference

This is a CLI tool for Taiwan-market SEO ranking and keyword clustering. It wraps DataForSEO and shares a Neon Postgres cache with `simple-seo-tools`.

## First-time setup (run if `seo init --check` fails or `seo` is missing)

The user's environment may be fresh. Before running any `seo` command, verify it's installed and configured:

```bash
seo init --check 2>&1 | jq .
```

| Result | What it means | What to do |
|---|---|---|
| `command not found: seo` | Not installed | `cd <repo> && uv sync --extra dev`, then prefix commands with `uv run` (e.g. `uv run seo cluster ...`) |
| `{"error": "config not set up"...}` or `config_valid: false` | No `~/.config/agent-seo-toolbox/config.toml` or no `.env` | See "config flow" below |
| `db_reachable: false` | `.env` missing `DATABASE_URL` or wrong | Ask user to paste DATABASE_URL into `~/.config/agent-seo-toolbox/.env` |
| `dataforseo_auth: "ok", db_reachable: true, config_valid: true` | All good | Proceed |

### Config flow (when `seo init --check` shows config invalid)

Two files are needed; **handle them differently**:

1. **`~/.config/agent-seo-toolbox/config.toml`** (non-secret) — own_domain, competitors. Drive this via the **`agent-seo-toolbox-init` skill**:
   - Use `AskUserQuestion` to gather `own_domain` and `competitors`
   - Run `seo init --non-interactive --own-domain X --competitors A,B,C`

2. **`~/.config/agent-seo-toolbox/.env`** (secret) — DATABASE_URL, DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD. **Do not ask the user for these in chat** (keeps secrets out of transcript). Instead instruct the user to:
   - Paste them from a teammate's shared `.env` (most teams do this), or
   - Open `$EDITOR ~/.config/agent-seo-toolbox/.env` themselves and add the three vars

After both are set, re-run `seo init --check` to confirm.

### When the user says "set up the SEO toolbox"

Invoke the `agent-seo-toolbox-init` skill — it orchestrates the steps above.

## Usage walkthrough — read this for concrete examples

**[docs/usage.md](docs/usage.md)** has end-to-end examples for both commands (input CSV format, output JSON shape, browser UI features, common patterns, cost notes, troubleshooting). Read it whenever the user asks "how do I use seo cluster" / "how does rank-check work" / before running a command on unfamiliar input.

## Quick decision tree

| User asks | Run |
|---|---|
| "Where does X URL rank for keyword Y?" | `seo rank-check "Y" "X"` |
| "Where does X URL rank for these N keywords?" (health check) | Serial loop over `seo rank-check` per keyword; see "Common patterns" below |
| "Cluster these keywords" / "Group by intent" | `seo cluster keywords.csv` |
| "Set up the toolbox" / first-time use | `seo init` (or invoke the `agent-seo-toolbox-init` skill) |
| "Verify config / test connectivity" | `seo init --check` |

## Output convention

**JSON to stdout by default.** Use `--pretty` only if the user asks for human formatting. Errors return nonzero exit + `{"error": "...", "code": "..."}`. Diagnostic info goes to stderr.

Pipe directly: `seo rank-check "本地 SEO 優化" "https://x.com/y" | jq '.organic_rank'`

## Commands

### `seo rank-check <keyword> <target_url>`

Find a target URL's rank for a keyword across AI Overview, Featured Snippet, and Organic results.

Output JSON schema:
```json
{
  "keyword": "...",
  "target_url": "...",
  "target_normalized": "...",
  "findings": [
    {"where": "ai_overview.reference|ai_overview.item|featured_snippet|organic", ...}
  ],
  "organic_rank": 1,
  "organic_total": 53,
  "in_ai_overview": true,
  "in_featured_snippet": false,
  "cache": {"hit": true, "age_seconds": 7200, "fetched_at": "2026-04-25T..."},
  "cost_usd": 0.0
}
```

`organic_rank` is `null` if not found in top ~60 organic. Cache hit: $0. Miss: ~$0.008–0.010 (depth=60 + AI Overview + PAA add-ons).

### `seo cluster <keywords.csv> [--threshold 0.3] [--method percentage|jaccard] [--output out.csv]`

Read a CSV with `keyword[,volume]` columns. Fetch top-10 organic SERPs per keyword (cache-first). Open an interactive HTML UI in the browser. User adjusts clusters via drag-drop and threshold slider, clicks Save. Server writes `cluster_state.json` and exits.

**stderr on start (immediately):** `{"server_port": ..., "state_path": "/tmp/seo-cluster-<runid>/cluster_state.json", "status": "awaiting_user"}`
**stdout after save:** `{"state_path": "...", "clusters": [{"primary": "...", "members": [...], "volume": N}, ...], "ungrouped": [...], "threshold_used": 0.3}`

Read full state at the path printed on stderr: `cat /tmp/seo-cluster-<runid>/cluster_state.json | jq .`

Cache hit per keyword: $0. Miss per keyword: ~$0.005–0.010 (depth=20 + AI Overview + PAA).

### `seo init [--own-domain X] [--competitors A,B] [--non-interactive] [--check]`

Writes `~/.config/agent-seo-toolbox/config.toml`. Without flags, prompts interactively (questionary). With `--non-interactive`, accepts values via flags only — used by the `agent-seo-toolbox-init` skill after `AskUserQuestion`.

Note: this command does NOT write `.env` (credentials must be edited manually to keep secrets out of transcripts).

`--check` validates current config and tests Neon + DataForSEO connectivity:
```json
{"config_valid": true, "db_reachable": true, "dataforseo_auth": "ok"}
```

## Common patterns

**"Check the rank, then suggest improvements":**
```
seo rank-check "本地 SEO 優化" "https://example.com/page" | jq .
# Read findings, organic_rank, in_ai_overview
# If rank > 5, examine top-ranking competitors via cached SERP data
```

**"Health check this list of keywords against our URL":** (batch mode, no CLI yet)
```
URL="https://example.com/page"
for kw in "kw1" "kw2" "kw3"; do
  seo rank-check "$kw" "$URL" | jq -c '{kw: .keyword, organic_rank, in_aio: .in_ai_overview, cache_hit: .cache.hit, cost: .cost_usd}'
done
# Then summarize: Top 3 / Page 1 / Page 2+ / Not ranked / AI Overview cited
# Cost rule: if N > 5, warn user of worst-case cost (N × ~$0.010) before running
# Native `seo batch-rank` CLI is planned — see docs/TODO.md
```

**"Cluster these and tell me what to write":**
```
seo cluster keywords.csv > /tmp/cluster_summary.json
# Read /tmp/seo-cluster-<runid>/cluster_state.json for full state
# For each cluster: primary keyword = focus for one page; members = supporting keywords
```

**"Setup":**
```
# If user has no config:
# 1. Use AskUserQuestion to gather: own_domain, competitor_domains
# 2. Run: seo init --non-interactive --own-domain ... --competitors ...
# 3. Tell user to manually create ~/.config/agent-seo-toolbox/.env with creds
#    (don't ask for credentials in chat — keeps them out of transcripts)
```

## Error codes

| Exit | Code | Meaning |
|---|---|---|
| 0 | — | Success, valid JSON on stdout |
| 1 | `config_invalid` | Run `seo init --check` to diagnose |
| 1 | `missing_dep` | Required Python package not installed (rare; reinstall) |
| 1 | `no_tty` | `seo init` called without `--non-interactive` from non-terminal |
| 1 | `empty_csv` | `seo cluster` got a CSV with no keywords |

## Environment

- Config: `~/.config/agent-seo-toolbox/config.toml`
- Secrets: `~/.config/agent-seo-toolbox/.env` (DATABASE_URL, DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)
- Cache: shared Neon Postgres `serp_cache` table; 7-day TTL
- Defaults target Taiwan: `location_code=2158`, `language_code=zh-TW`, mobile/iOS

## Registry — single source of truth for cross-module constants

`src/seo_toolbox/registry.py` is the canonical home for "magic" values used
across the codebase. **Add new constants here, not inline.** When you build a
new command/page that needs a depth, TTL, market code, brand string, or color
token, import from registry instead of hardcoding.

Groups:

| Class | Owns |
|---|---|
| `Brand` | `NAME` — used in template header + saved page |
| `Market` | `LOCATION_CODE` / `LANGUAGE_CODE` / `DEVICE` / `OS` — DataForSEO defaults |
| `SerpFetch` | `CLUSTER_DEPTH` (20), `RANK_CHECK_DEPTH` (60) |
| `Cache` | `SERP_TTL_DAYS` (7), `EXPANSION_TTL_DAYS` (30), `VOLUME_TTL_DAYS` (30, planned) |
| `Cluster` | `DEFAULT_THRESHOLD` (0.30), `DEFAULT_METHOD` ("percentage"), `SESSION_SECONDS` |
| `UI` | `SIDEBAR_WIDTH_PX` — mirrors `--sidebar-w` in cluster.css |
| `Colors` | `OWN` / `COMPETITOR` / `AUTHORITY` — mirrors `:root` color vars in cluster.css |
| `package_version()` | resolves installed version via importlib.metadata |

**CSS sync rule:** colors and dimensions live primarily in `cluster.css :root`;
`Colors` and `UI` mirror them so backend templates / JSON payloads can reference
the same values. If you change a color, update both.

**Wiring pattern:**
```python
from seo_toolbox.registry import Cache, Cluster, Market, SerpFetch, Brand

# config.py dataclass defaults:
location_code: int = Market.LOCATION_CODE
cluster_threshold: float = Cluster.DEFAULT_THRESHOLD
serp_ttl_days: int = Cache.SERP_TTL_DAYS

# command modules:
async def fetch(..., depth: int = SerpFetch.CLUSTER_DEPTH): ...
```

Frontend reads brand/version/state_path from the rendered Jinja payload, not
from registry directly. The backend bridges them.

## Methodology

See `docs/methodology.md` for academic foundations (Zhang et al. SIGIR '11, Keyword Insights 2021), similarity metrics (Jaccard / percentage / shared count), and DataForSEO cost model.

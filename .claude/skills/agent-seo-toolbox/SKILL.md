---
name: agent-seo-toolbox
description: Taiwan-market SEO ranking and keyword clustering. Use when the user asks "where does X rank for Y", "cluster these keywords", "what's our SEO position for ___", or anything involving Google SERP analysis for Taiwan/zh-TW. Wraps DataForSEO + shared Neon cache.
---

# agent-seo-toolbox

Use this skill when working with the `agent-seo-toolbox` CLI (`seo` command) for SEO ranking and keyword clustering analysis.

## How to use

The `seo` CLI is on PATH after `uv tool install`. Full reference is in the repo's `CLAUDE.md` — auto-loaded if you cd into the repo directory.

### Common flows

**Rank check:**
```bash
seo rank-check "<keyword>" "<target_url>" | jq .
```
Returns JSON with `organic_rank`, `in_ai_overview`, `in_featured_snippet`, cache info, and findings list.

**Clustering:**
```bash
seo cluster <keywords.csv> [--threshold 0.3]
```
Opens a browser UI for the user to refine clusters. Stderr emits `{"status": "awaiting_user", ...}` immediately. Stdout emits final clusters after the user clicks Save. Read the full state from the path printed in stderr.

**Configuration check:**
```bash
seo init --check | jq .
```
If `config_valid: false`, the user needs to run `seo init` or invoke the `agent-seo-toolbox-init` skill.

## When NOT to use

- US/EN market questions — defaults are Taiwan-specific. Override via flags or note the limitation.
- Bulk URL crawling, on-page SEO audits — out of scope.
- Real-time keyword research expansion — `seo expand` is post-MVP, not yet implemented.

## Cost transparency

Every command prints `cost_usd`. Cache hits = $0. Inform the user of cost before bulk operations (e.g., clustering 100 keywords = up to ~$1).

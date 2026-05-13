---
name: agent-seo-toolbox
description: Taiwan-market SEO ranking and keyword clustering. Use when the user asks "where does X rank for Y", "cluster these keywords", "what's our SEO position for ___", or anything involving Google SERP analysis for Taiwan/zh-TW. Wraps DataForSEO + shared Neon cache.
---

# agent-seo-toolbox

Use this skill when working with the `agent-seo-toolbox` CLI (`seo` command) for SEO ranking and keyword clustering analysis.

## How to use

The `seo` CLI is on PATH after `uv tool install`. Full reference is in the repo's `CLAUDE.md` — auto-loaded if you cd into the repo directory.

### Common flows

**Rank check (single keyword × single URL):**
```bash
seo rank-check "<keyword>" "<target_url>" | jq .
```
Returns JSON with `organic_rank`, `in_ai_overview`, `in_featured_snippet`, cache info, and findings list.

**Batch rank check (N keywords × same URL — "我們在這些字各排第幾"):**

When the user gives multiple keywords against one target URL (e.g. health-check, monthly tracking, "幫我看這 20 個字"), loop `seo rank-check` and aggregate. No batch CLI exists yet (planned, see `docs/TODO.md`).

Template:
```bash
URL="https://example.com/page"
for kw in "本地 SEO 優化" "GEO 在地搜尋優化" "SEO 工具推薦"; do
  seo rank-check "$kw" "$URL" \
    | jq -c '{kw: .keyword, organic_rank, in_aio: .in_ai_overview, in_fs: .in_featured_snippet, cache_hit: .cache.hit, cost: .cost_usd}'
done
```

Then summarize to the user as a table (markdown), grouped by:
- **Top 3** (organic_rank ≤ 3)
- **Page 1** (4 ≤ organic_rank ≤ 10)
- **Page 2+** (organic_rank > 10)
- **Not ranked** (organic_rank null)
- **AI Overview cited** — list separately, since AIO citation is independent of rank

**Cost-before-you-run rule:** If N > 5, estimate worst-case cost before running and tell the user (e.g. "20 misses × ~$0.010 = up to $0.20; cache hits free"). Don't surprise them.

If the user has a CSV with a `keyword` column, read it in shell (`cut -d, -f1 | tail -n +2`) rather than asking them to paste keywords inline.

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

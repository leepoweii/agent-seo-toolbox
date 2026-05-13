# TODO

## Batch rank-check CLI (backlog)

**Current state:** `seo rank-check` only takes one keyword × one URL. Batch use ("這 20 個字各排第幾") today goes through Claude looping the single-call CLI (see `agent-seo-toolbox` skill's batch pattern).

**Why promote it to CLI:**
- Parallel calls to DataForSEO (asyncio.gather) — N× faster than serial subprocess loop
- One JSON output with summary stats (ranked / not_ranked / in_aio counts, total cost) — easier to consume from any caller, not just Claude
- Usable from cron / shell pipelines without an LLM in the loop

**Sketch:**
```bash
seo batch-rank <keywords.csv> <target_url> [--concurrency 5]
```
- CSV: `keyword` column required (volume optional, ignored for rank-check)
- Output: `{target_url, results: [...], summary: {total, ranked, in_aio, in_fs, total_cost_usd, cache_hits}}`
- Implementation: new `src/seo_toolbox/commands/batch_rank.py`, reuses `rank_check` lookup function, wraps `asyncio.gather`

**Not a priority** — Claude-driven loop works fine for typical 10–30 keyword batches. Promote when someone wants this from cron or from a non-Claude caller.

---

## Volume fetching (next feature branch: `feature/volume-fetch`)

**Trust user-provided volumes; fetch missing ones; never pollute cache with user values.**

### Behavior
- CSV `volume` column tri-state: present + >0 → user-provided; absent or blank → fetch
- 0 should also be treated as "fetch" (not "trusted zero")
- User values: used as-is, **not written to cache**
- Fetched values: written to a new `volume_cache` table, 30-day TTL

### New table
```
volume_cache(keyword, location_code, language_code, volume, fetched_at)
PRIMARY KEY (keyword, location_code, language_code)
```

### API
- `keywords_data/google_ads/search_volume/live` (DataForSEO)
- ~$0.05 per 1000 keywords — batch all missing kws into one call
- Same `location_code` / `language_code` as SERP fetches (Taiwan, zh-TW)

### CLI flag
- `--fetch-volumes` (opt-in, default off) — avoid surprise billing
- Or `--no-fetch-volumes` for opt-out — decide based on UX preference

### Output annotation
JSON output should label each volume's provenance:
```json
{
  "volumes": {
    "日本樂天購物": {"value": 2900, "source": "user"},
    "日本樂天網購": {"value": 90, "source": "dataforseo", "cache_hit": true},
    "日本樂天寄台灣": {"value": 50, "source": "dataforseo", "cache_hit": false}
  }
}
```

### Why
- User-provided volumes come from inconsistent sources (GSC, Ahrefs, Ubersuggest) — can't conflate with DataForSEO numbers in shared cache
- Currently missing volumes default to 0, which makes greedy primary selection effectively alphabetical
- Tri-state parse needed: distinguish "user explicitly says 0" (rare, trust) vs "no value" (fetch)

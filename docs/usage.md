# Usage — examples & patterns

Walk-through of the two commands the toolbox currently ships. Read this when the user asks "how do I use seo cluster" or "where does X rank for Y" and you need a concrete example to follow.

All commands print **JSON to stdout**; pipe to `jq` for inspection. Diagnostic info goes to stderr.

---

## 1. `seo rank-check` — find a URL's rank for a keyword

### Example

```bash
seo rank-check "本地 SEO 優化" "https://example.com/local-seo"
```

Output:

```json
{
  "keyword": "本地 SEO 優化",
  "target_url": "https://example.com/local-seo",
  "target_normalized": "example.com/local-seo",
  "findings": [
    {"where": "organic", "rank": 4, "rank_absolute": 9, "title": "...", "url": "..."},
    {"where": "ai_overview.reference", "title": "...", "url": "..."}
  ],
  "organic_rank": 4,
  "organic_total": 53,
  "in_ai_overview": true,
  "in_featured_snippet": false,
  "cache": {"hit": true, "age_seconds": 7200, "fetched_at": "2026-04-25T..."},
  "cost_usd": 0.0
}
```

### How to read it

| Field | Meaning |
|---|---|
| `findings[]` | Every place the URL appears — organic, AI Overview reference/item, Featured Snippet |
| `organic_rank` | Position in pure organic results (1 = top); `null` if not in top ~60 |
| `rank_absolute` | Position counting all SERP elements (ads, AIO, etc.) |
| `in_ai_overview` | Quick boolean: is this URL cited in Google's AI Overview? |
| `cache.hit` | `true` = $0; `false` = ~$0.008–0.010 |

### Common patterns

**"Check rank, then plan improvements":**
```bash
seo rank-check "本地 SEO 優化" "https://example.com/page" | jq .
# Read findings, organic_rank, in_ai_overview
# If rank > 5 or not in AI Overview, examine top-ranking competitors via cached SERP data
```

**Batch check across keywords (parallel):**
```bash
for kw in "本地 SEO 優化" "GEO 在地搜尋優化" "SEO 工具推薦"; do
  seo rank-check "$kw" "https://example.com/page" | jq -c '{kw: .keyword, rank: .organic_rank, aio: .in_ai_overview}'
done
```

---

## 2. `seo cluster` — group keywords by SERP overlap

Reads a CSV with `keyword[,volume]`, fetches top-10 organic SERP per kw (cache-first), opens an interactive browser UI for the user to drag-drop into clusters, writes final state to JSON.

### Input CSV

```csv
keyword,volume
日本樂天購物,2900
日本樂天購物教學,170
日本樂天怎麼買,170
日本樂天網購,90
```

`volume` column is optional. Without it, all volumes default to 0 and clustering uses alphabetical primary selection.

### Run it

```bash
seo cluster /path/to/keywords.csv
```

**Two outputs:**

- **stderr (immediate)** — server info while user interacts:
  ```json
  {"server_port": 64718, "state_path": "/tmp/seo-cluster-20260427-013943-3ab49c/cluster_state.json", "status": "awaiting_user"}
  ```
- **stdout (after user clicks Save)** — final clustered state:
  ```json
  {
    "state_path": "/tmp/seo-cluster-…/cluster_state.json",
    "clusters": [
      {"primary": "日本樂天購物", "members": ["日本樂天購物", "日本樂天購物教學", ...], "volume": 3240}
    ],
    "ungrouped": [],
    "threshold_used": 0.30
  }
  ```

### Browser UI features

The user sees:
- **Cluster cards** — each shows primary keyword, total volume, member kw rows
- **Drag-drop** between clusters — threshold-aware: drops are blocked if SERP overlap < threshold OR if dragged kw's volume > target primary's volume
- **Threshold slider** — top of page; recomputes greedy grouping live
- **+ New cluster** placeholder at end of grid — drop a kw there to spawn a new cluster
- **Domain pills** on each row (green/orange/red counts) — own/authority/competitor URLs in overlap
- **Click any kw** to pin its full SERP into the right sidebar:
  - AI Overview (markdown rendered, expandable)
  - Featured Snippet
  - People Also Ask
  - Top-10 organic with overlap highlighted
- **Hover any kw** to dim/light other rows by SERP overlap with the hovered kw

### Reading the saved state

Full state JSON is at `state_path` printed on stderr. Always read it for the complete result:

```bash
cat /tmp/seo-cluster-<runid>/cluster_state.json | jq .
```

### Common patterns

**"Cluster these and tell me what to write":**
```bash
seo cluster keywords.csv > /tmp/cluster_summary.json
# After user saves: read /tmp/seo-cluster-<runid>/cluster_state.json
# For each cluster: primary keyword = focus for one page; members = supporting keywords
```

**"Custom threshold for a tighter / looser grouping":**
```bash
seo cluster keywords.csv --threshold 0.5      # 5/10 shared URLs minimum
seo cluster keywords.csv --threshold 0.2      # looser; 2/10 minimum
```

**"Use jaccard instead of percentage":**
```bash
seo cluster keywords.csv --method jaccard --threshold 0.3
```
(Default `percentage` is industry standard. `jaccard` is for academic / research workflows.)

---

## Cost & cache notes

- **Cache hit = $0**, lasts 7 days (SERP TTL)
- **rank-check miss**: ~$0.008–0.010 per keyword (depth=60 + AI Overview + PAA add-ons)
- **cluster miss**: ~$0.005–0.010 per keyword (depth=20 + add-ons)
- All cache rows share the team Neon DB — your colleague's SERP fetches benefit you and vice versa

## When things break

| Symptom | Fix |
|---|---|
| `command not found: seo` | `cd repo && uv sync --extra dev`; prefix with `uv run` |
| `{"error": "config_invalid"}` | Run `seo init --check` to see what's missing; see CLAUDE.md "first-time setup" |
| `db_reachable: false` | `.env` missing or DATABASE_URL wrong; ask user to paste from teammate |
| `cluster` browser doesn't open | Check stderr for `server_port`; visit `http://localhost:<port>` manually |
| Browser opens but page is blank | Hit reload; the static assets ship from the same server |

For the agent-side decision tree (which command to run for which question), see [CLAUDE.md](../CLAUDE.md).

# Methodology

How `agent-seo-toolbox` clusters keywords and ranks pages, with the academic and industry sources that ground the approach.

## Why SERP-overlap clustering

Modern Google ranks **pages**, not keywords. A single high-quality page can simultaneously rank for many related keywords if Google sees them as variations of the same intent.

The way to detect this: **look at Google's own SERPs**. If two keywords return mostly the same top-10 URLs, Google has already decided they share intent. So you write **one page** to target both. If their SERPs are completely different, you need **separate pages**.

This is the central premise of modern keyword clustering: use Google's actual ranking decisions as ground truth, rather than guessing intent from word similarity.

### Underlying academic principle

Zhang et al. (SIGIR '11) formalized the **Search Result Overlap Ratio (SROR)** to quantify how much two related queries return the same documents. This is the closest formal articulation of "if SERPs overlap, queries share intent."

> Zhang, Y., Sun, L., Wen, J.-R., et al. *Query term ranking based on search results overlap.* SIGIR '11. DOI: [10.1145/2009916.2010145](https://dl.acm.org/doi/10.1145/2009916.2010145)

Adjacent IR work:

- Guo, J. et al. *Intent-Aware Query Similarity.* CIKM '11. [PDF](https://jiafengguo.github.io/2011/2011-Intent-Aware%20Query%20Similarity.pdf) — Jaccard/cosine pair-wise similarity on retrieved sets in the context of search intent.
- Sadikov, E. et al. *Clustering query refinements by user intent.* WWW '10 — uses click-through (related signal) to cluster query intents.
- Manning, C. D., Raghavan, P., Schütze, H. *Introduction to Information Retrieval.* Cambridge University Press, 2008. Chapter 6 — Jaccard on retrieved document sets is textbook IR.

### Industry operationalization

The exact recipe — "cluster keywords if their top-10 SERPs share ≥ N URLs" — was popularized by **Keyword Insights** in 2021 and is now the de-facto standard across SEO tools (Cluster AI, Surfer SEO, ContentKing).

> Keyword Insights. *Keyword Clustering: Probably The Best Guide.* [keywordinsights.ai/blog/keyword-clustering-guide](https://www.keywordinsights.ai/blog/keyword-clustering-guide/)
> Default rule: ≥ 30% top-10 URL overlap (Jaccard ≈ 0.3) → same cluster.

**Honest caveat:** the precise "Jaccard on top-10 URLs to cluster keywords" recipe is industry practice rather than a formally cited academic method. The IR literature establishes the underlying premise; the SEO industry operationalized it.

## Similarity metrics

Three metrics are computed for every keyword pair:

| Metric | Formula | Range | Reads as |
|---|---|---|---|
| **Raw shared count** | `\|A ∩ B\|` | 0 – list size | "Share 4 URLs" |
| **Jaccard** | `\|A ∩ B\| / \|A ∪ B\|` | 0 – 1 | "Share 25% of combined URLs" |
| **Percentage** (Szymkiewicz–Simpson) | `\|A ∩ B\| / min(\|A\|, \|B\|)` | 0 – 1 | "80% of smaller SERP is contained in bigger" |

**Default: Jaccard.** Symmetric, normalized 0–1, matches industry default and the existing simple-seo-tools algorithm. Threshold default `0.3` ≈ "share at least 3-4 URLs out of 10."

**When percentage helps:** parent/child topic relationships. If keyword B's narrow-intent SERP is a subset of keyword A's broad-intent SERP, percentage spikes (containment) while Jaccard stays moderate.

**Why we display all three in the UI:** algorithm uses Jaccard for thresholds (mathematical purity); humans read raw count more easily ("4 shared URLs" vs "0.25 Jaccard"). Showing both lets users adjust the threshold by whichever feels intuitive.

## SERP data used for similarity

Similarity is computed on **the top 10 organic URLs** for each keyword. Specifically:

```
1. Call DataForSEO with depth=N (20 for cluster, 60 for rank-check — see below).
2. Filter response to type == 'organic' only.
   (Discard: ads, AI Overview, featured snippet, People Also Ask,
    image pack, video carousel, knowledge graph, local pack, etc.)
3. Take the first 10 organic items.
4. Normalize URLs (see "URL normalization" below).
5. Use these 10 URLs as the keyword's SERP fingerprint.
```

**Different commands fetch different depths:**

- **Cluster** uses depth=20 (~2 SERP pages, ~$0.005–0.010 with add-ons). Sufficient for top-10 organic.
- **Rank-check** uses depth=60 (~6 SERP pages, ~$0.008–0.010 with add-ons). Covers the "max 60 organic" criterion — pages 1–6 of Google with buffer for SERP features that consume slots.

DataForSEO bills per 10-result SERP page, so depth scales linearly: depth=60 costs ~3× the base depth fee of depth=20 (add-ons are flat). The cache stores the `depth_fetched` value in `serp_data.metadata` so a depth=20 cluster cache can be detected as insufficient when rank-check needs deeper data — in that case, refetch at depth=60 and overwrite.

Modern Taiwan SERPs frequently include AI Overview, PAA, featured snippets, ads, and image/video carousels that consume slots. depth=20 reliably yields ≥10 organic; depth=60 reliably yields ~50 organic.

**Why organic-only:**

- **Ads** are paid placement, not intent signal. Two unrelated keywords might share an advertiser — false positive.
- **AI Overview, featured snippets, PAA** are derivative — they pull from organic results, so including them double-counts the same URLs.
- **Industry and academic standard**: Zhang et al. (SIGIR '11), Keyword Insights, and every modern SEO clustering tool compare organic results exclusively.

## Additional SERP data captured for analysis

Although similarity is computed only on top-10 organic, the full SERP response is parsed and stored for richer analysis. Each cached SERP record includes:

| Field | What it captures | Why it matters |
|---|---|---|
| `ai_overview` | Markdown text + cited references (URLs and titles) | **GEO / AI SEO** — which sources Google's generative answer cites for this query. Identifies AI-citation opportunities and competitor visibility in AI Overview. |
| `featured_snippet` | URL, title, snippet text | The page Google considers most authoritative for a direct answer. High-value real estate. |
| `people_also_ask` | List of related questions + their answer URLs | Reveals adjacent intent and content gap opportunities. Useful for content brief expansion. |
| `serp_item_types` | Ordered list of all SERP feature types present | "Does this query trigger AI Overview? Knowledge graph? Local pack?" — informs content format decisions. |
| `total_results` | Google's reported result count | Coarse difficulty signal. |

These fields are stored in the `serp_cache` table (Neon, shared with simple-seo-tools) under the existing `serp_data` JSONB column — no schema change required.

**Used by clustering:** organic only.
**Used by enhanced analysis:** all of the above. Future commands like `seo brief` and `seo geo-audit` will read these fields to generate content briefs and AI Overview citation reports.

## Clustering algorithm

Volume-anchored greedy grouping, identical to simple-seo-tools' `greedyVolumeGrouping`:

```
1. Compute pairwise similarity matrix for all keyword pairs.
2. Sort keywords by search volume, descending.
3. For each unassigned keyword (highest volume first):
     a. It becomes a cluster's "primary" (head term).
     b. Walk remaining unassigned keywords. If similarity(primary, candidate)
        ≥ threshold AND candidate.volume ≤ primary.volume → add to cluster.
4. Keywords not added to any cluster end up in "ungrouped".
```

### Why volume-anchored, not pure graph clustering

Pure graph community detection (e.g., connected components above a threshold) treats all keywords as equal nodes. But SEO content production needs a **focus keyword** for:

- Title tag, H1, URL slug
- Meta description
- Internal link anchors
- The "write a page about X" content brief

Volume-anchored grouping promotes the highest-volume keyword in each cluster to "primary." Other members are "supporting keywords." This aligns with editorial workflows: a writer can be told "write about *primary*, naturally covering *supporting1, supporting2...*"

## URL normalization

Before computing overlap, URLs are normalized to avoid spurious differences:

- Lowercase hostname
- Strip leading `www.`
- Strip trailing slash from path
- Sort query parameters alphabetically
- Strip tracking parameters: `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `fbclid`, `gclid`, `ref`, `source`

Same normalization as `apps/web-v2/src/lib/grouping.ts` in simple-seo-tools.

## Rank-check methodology

For a target URL given a keyword, fetch one DataForSEO SERP (depth=60, mobile/iOS, country-level Taiwan, zh-TW) and report:

- **AI Overview citation** — does the URL appear in `ai_overview.references` or `ai_overview.items`?
- **Featured Snippet** — does the URL match `featured_snippet.url`?
- **Organic rank** — position among `organic`-typed items only (1-indexed). Sponsored/paid/PAA/video/image rows excluded.
- **rank_absolute** — position counting all SERP features (for context, not the headline number).

Why mobile/iOS: validated against real Chrome rankings; matches what Taiwan users actually see (~80%+ mobile traffic).

Why depth=60: rank-check must locate the target URL even if it ranks at position 30+, capped at "max 60 organic" per business logic. See "SERP data used for similarity" above for full pricing breakdown.

## Output convention

Every CLI command outputs **structured JSON to stdout by default** (designed for Claude Code to parse). Diagnostic output (progress, cache hits, etc.) goes to stderr. `--pretty` switches to human-readable formatting.

- Success: exit 0, JSON object on stdout
- Failure: nonzero exit, `{"error": "...", "code": "..."}` on stdout

This convention follows modern CLI tools (`gh`, `jq`, `kubectl --output=json`) and lets Claude pipe results directly: `seo rank-check ... | jq '.organic_rank'`.

## DataForSEO cost model

Every SERP API call has a base depth cost plus optional add-ons. Sourced from [DataForSEO docs](https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/) (verified 2026-04-25).

### Base cost — billed per 10-result SERP page

| Depth | Pages billed | Approx. base ($) |
|---|---|---|
| 10 | 1 | ~$0.0006 |
| 20 | 2 | ~$0.0012 |
| 60 | 6 | ~$0.0036 |
| 100 | 10 | ~$0.0060 |
| 200 (max) | 20 | ~$0.012 |

Base rate per page (~$0.0006) is approximate at the lowest pricing tier; volume-tiered discounts apply to higher monthly spend.

### Add-ons (extras on top of base)

| Add-on | Param | Cost | Refund |
|---|---|---|---|
| AI Overview content | `load_async_ai_overview=true` | +$0.002 | Refunded if AIO absent or not async |
| People Also Ask answers | `people_also_ask_click_depth=3` | +$0.00015 per click, max +$0.00045 | Refunded for clicks not performed |
| Element rectangles | `calculate_rectangles=true` | +$0.002 | not used |
| Search operators (`site:`, `inurl:`) | n/a | 5× multiplier on whole task | not used |

### Toolbox configuration

Both `seo cluster` and `seo rank-check` request:
- `load_async_ai_overview=true` — required for AI Overview citation tracking and `seo rank-check`'s "in_ai_overview" output
- `people_also_ask_click_depth=3` — captures PAA questions + answer URLs for enhanced analysis

Fixed add-on overhead per call: ~$0.00245 when AIO is present (less if refunded).

### Per-command cost (typical)

| Command | Depth | Theoretical | Observed (real call) |
|---|---|---|---|
| `seo cluster` (one keyword) | 20 | ~$0.0037 | ~$0.005–0.010 |
| `seo rank-check` (one keyword) | 60 | ~$0.0061 | ~$0.008–0.010 |

The "observed" range is higher than theoretical because the base per-page rate at our pricing tier is moderately above the floor, and AI Overview was present in test queries (no refund). Cache hits cost $0.

## Data sources

- **DataForSEO** for live SERP data (`/serp/google/organic/live/advanced` endpoint) and keyword expansion (`/dataforseo_labs/google/related_keywords/live`). Validated via real-Chrome cross-check on Taiwan ophthalmology keywords (2026-04-25).
- **Shared cache on Neon Postgres** (project: simple-seo-tools) — every team member's lookup populates the cache; subsequent identical lookups are free. Cache TTL: 7 days for SERPs, 30 days for keyword expansions.

## What this tool deliberately does NOT do

- **Pure semantic similarity** (word embeddings, BERT) — fails because semantically similar keywords often have different intent (e.g., "buy iphone" vs "iphone reviews" share words, have different SERPs).
- **Keyword stem grouping** — too crude, misses synonyms.
- **Manual taxonomies** — doesn't scale, gets stale.
- **Pure graph community detection** — produces clusters with no head term, awkward for content briefs.

These are the same exclusions documented in the source IR literature and validated by industry adoption of SERP-overlap as the dominant approach since 2021.

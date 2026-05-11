---
name: agent-seo-toolbox-init
description: Use when user says "set up the SEO toolbox", "configure agent-seo-toolbox", "change my domain", "update competitors", or any time own domain / competitor list needs to be set or updated — always ask, never skip.
---

# agent-seo-toolbox-init

Always ask the user for own domain and competitors via AskUserQuestion, then write config. Never skip even if config already exists.

## Steps

1. **Ask via AskUserQuestion (always — no skip):**
   - Both questions must use blank/generic options so the user always types via "Other" free-text input. Never pre-fill with known domain values.
   - Question 1: "What is your own domain?" — options: ["輸入 domain", "略過（保留現有）"]
   - Question 2: "List competitor domains, comma-separated" — options: ["輸入競爭對手", "略過（保留現有）"]

2. **Write the config:**
   ```bash
   uv run seo init --non-interactive --own-domain "<answer1>" --competitors "<answer2>"
   ```

3. **Verify:**
   ```bash
   uv run seo init --check | jq .
   ```
   Confirm `config_valid: true, db_reachable: true, dataforseo_auth: "ok"`.

4. **If db or auth fails**, tell the user to edit `~/.config/agent-seo-toolbox/.env`:
   ```
   DATABASE_URL=...
   DATAFORSEO_LOGIN=...
   DATAFORSEO_PASSWORD=...
   ```
   Never ask for credentials in chat — keeps them out of transcripts.

## Why always ask?

Config drifts as campaigns change. Prompting every time ensures the active domain/competitor set matches the current task, not a stale file.

"""End-to-end smoke tests using `claude -p` real subprocess.

Requires:
  - `claude` CLI on PATH (Claude Code installed and authenticated)
  - Working ~/.config/agent-seo-toolbox/.env with prod creds
  - The agent-seo-toolbox skills installed (symlinked into ~/.claude/skills/)

Cost: ~$0.05–$0.10 per test (Claude API + DataForSEO).
Run only in pre-push, not pre-commit.
"""
import shutil
import subprocess

import pytest


@pytest.fixture(scope="module")
def claude_available():
    if not shutil.which("claude"):
        pytest.skip("claude CLI not on PATH")


def test_init_check_via_claude(claude_available):
    """Claude should be able to invoke `seo init --check` and report whether config is valid."""
    result = subprocess.run(
        ["claude", "-p",
         "Run `seo init --check` and tell me whether config_valid is true or false. "
         "One word answer only."],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout.lower()
    assert "true" in out or "false" in out


def test_rank_check_via_claude(claude_available):
    """Claude should invoke seo rank-check and report the organic rank as a number."""
    result = subprocess.run(
        ["claude", "-p",
         "Use seo rank-check to find the organic rank of "
         "https://example.com/local-seo for keyword 本地 SEO 優化. "
         "Reply with just the rank number (e.g. 4) — no other text."],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr
    # Expect a digit somewhere in the response
    assert any(c.isdigit() for c in result.stdout), f"no digit in output: {result.stdout!r}"

"""Integration test for `seo init` — uses subprocess + isolated XDG_CONFIG_HOME."""

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_init_non_interactive_writes_config(tmp_path):
    isolated_config = tmp_path / "agent-seo-toolbox"
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path)}
    result = subprocess.run(
        [
            "uv",
            "run",
            "seo",
            "init",
            "--own-domain",
            "example.com",
            "--competitors",
            "a.com,b.com",
            "--non-interactive",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    output = json.loads(result.stdout)
    assert output["config_path"].endswith("config.toml")
    assert "domains.own" in output["saved_keys"]
    assert "domains.competitors" in output["saved_keys"]

    cfg_text = (isolated_config / "config.toml").read_text()
    assert 'own = "example.com"' in cfg_text
    assert '"a.com"' in cfg_text


def test_init_non_interactive_with_only_own_domain(tmp_path):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path)}
    result = subprocess.run(
        ["uv", "run", "seo", "init", "--own-domain", "solo.com", "--non-interactive"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "domains.own" in output["saved_keys"]
    assert "domains.competitors" not in output["saved_keys"]


def test_init_check_mode_returns_status_json(tmp_path):
    """--check returns JSON with config_valid/db_reachable/dataforseo_auth keys.

    Without creds set, it should return config_valid: false and exit 1.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "DATAFORSEO_"))}
    env["XDG_CONFIG_HOME"] = str(tmp_path)
    result = subprocess.run(
        ["uv", "run", "seo", "init", "--check"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    output = json.loads(result.stdout)
    assert "config_valid" in output
    assert "db_reachable" in output
    assert "dataforseo_auth" in output
    assert output["config_valid"] is False
    assert result.returncode == 1


def test_init_interactive_without_tty_returns_error(tmp_path):
    """Without --non-interactive and no TTY, init should error cleanly, not hang."""
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path)}
    result = subprocess.run(
        ["uv", "run", "seo", "init"],  # no --non-interactive, no TTY (subprocess pipe)
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=10,
    )
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["code"] == "no_tty"

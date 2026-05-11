import pytest

from seo_toolbox.config import load_config


@pytest.fixture
def tmp_global_dir(tmp_path, monkeypatch):
    """Redirect XDG_CONFIG_HOME so tests don't touch real config."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "agent-seo-toolbox"


def test_built_in_defaults_when_no_files(tmp_global_dir, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATAFORSEO_LOGIN", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)
    monkeypatch.delenv("DATAFORSEO_SANDBOX", raising=False)
    cfg = load_config()
    assert cfg.location_code == 2158
    assert cfg.language_code == "zh-TW"
    assert cfg.device == "mobile"
    assert cfg.os == "ios"
    assert cfg.cluster_threshold == 0.3


def test_global_toml_overrides_defaults(tmp_global_dir):
    tmp_global_dir.mkdir(parents=True)
    (tmp_global_dir / "config.toml").write_text(
        '[domains]\nown = "example.com"\ncompetitors = ["a.com", "b.com"]\n'
        "[defaults]\ncluster_threshold = 0.5\n"
    )
    cfg = load_config()
    assert cfg.own_domain == "example.com"
    assert cfg.competitor_domains == ["a.com", "b.com"]
    assert cfg.cluster_threshold == 0.5


def test_project_toml_overrides_global(tmp_global_dir, tmp_path, monkeypatch):
    tmp_global_dir.mkdir(parents=True)
    (tmp_global_dir / "config.toml").write_text('[domains]\nown = "global.com"\n')
    project = tmp_path / "project"
    project.mkdir()
    (project / "agent-seo-toolbox.toml").write_text('[domains]\nown = "project.com"\n')
    monkeypatch.chdir(project)
    cfg = load_config()
    assert cfg.own_domain == "project.com"


def test_explicit_overrides_beat_files(tmp_global_dir):
    tmp_global_dir.mkdir(parents=True)
    (tmp_global_dir / "config.toml").write_text('[domains]\nown = "global.com"\n')
    cfg = load_config(overrides={"own_domain": "flag.com"})
    assert cfg.own_domain == "flag.com"


def test_env_loads_secrets(tmp_global_dir, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATAFORSEO_LOGIN", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)
    tmp_global_dir.mkdir(parents=True)
    (tmp_global_dir / ".env").write_text(
        "DATABASE_URL=postgresql://test\n"
        "DATAFORSEO_LOGIN=user@example.com\n"
        "DATAFORSEO_PASSWORD=secret\n"
    )
    cfg = load_config()
    assert cfg.database_url == "postgresql://test"
    assert cfg.dataforseo_login == "user@example.com"
    assert cfg.dataforseo_password == "secret"


def test_unknown_toml_keys_ignored(tmp_global_dir):
    """Unknown TOML keys should be silently ignored, not crash or set unknown attrs."""
    tmp_global_dir.mkdir(parents=True)
    (tmp_global_dir / "config.toml").write_text(
        '[defaults]\nfoo_unknown = "bar"\nlocation_code = 9999\n[unknown_section]\nx = 1\n'
    )
    cfg = load_config()
    assert cfg.location_code == 9999  # known key applied
    assert not hasattr(cfg, "foo_unknown")  # unknown key not set
    assert not hasattr(cfg, "x")  # unknown section ignored

"""Smoke test for the cluster frontend template."""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "seo_toolbox" / "frontend"


def test_frontend_files_exist():
    assert (FRONTEND_DIR / "cluster.html.j2").exists()
    assert (FRONTEND_DIR / "cluster.js").exists()
    assert (FRONTEND_DIR / "cluster.css").exists()


def test_template_renders_with_sample_data():
    import json

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    def tojson_unicode(value, **kwargs):
        return json.dumps(value, ensure_ascii=False)

    env = Environment(
        loader=FileSystemLoader(str(FRONTEND_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tojson"] = tojson_unicode
    template = env.get_template("cluster.html.j2")
    html = template.render(
        keywords=["SEO 工具", "SEO 關鍵字工具"],
        volumes={"SEO 工具": 1000, "SEO 關鍵字工具": 500},
        serps={
            "SEO 工具": ["https://target.com/page", "https://other.com"],
            "SEO 關鍵字工具": ["https://target.com/page", "https://other.com"],
        },
        serp_features={
            "SEO 工具": {"ai_overview": None, "featured_snippet": None, "paa": []},
            "SEO 關鍵字工具": {"ai_overview": None, "featured_snippet": None, "paa": []},
        },
        jaccard={
            "SEO 工具": {"SEO 工具": 1.0, "SEO 關鍵字工具": 0.8},
            "SEO 關鍵字工具": {"SEO 工具": 0.8, "SEO 關鍵字工具": 1.0},
        },
        shared_count={
            "SEO 工具": {"SEO 工具": 2, "SEO 關鍵字工具": 1},
            "SEO 關鍵字工具": {"SEO 工具": 1, "SEO 關鍵字工具": 2},
        },
        initial_clusters=[
            {"primary": "SEO 工具", "members": ["SEO 工具", "SEO 關鍵字工具"], "volume": 1500}
        ],
        ungrouped=[],
        domains={
            "own": "target.com",
            "competitors": ["competitor.com"],
            "authority_tlds": [".gov", ".edu"],
        },
        threshold=0.3,
        session_seconds=1800,
    )
    assert "<!DOCTYPE html>" in html
    assert "SEO 工具" in html
    assert 'id="threshold"' in html
    assert 'id="save"' in html
    assert "SortableJS" in html or "sortablejs" in html.lower()  # CDN script reference
    assert 'id="countdown"' in html


def test_javascript_has_required_functions():
    js = (FRONTEND_DIR / "cluster.js").read_text()
    # Should reference Sortable, threshold, save, countdown
    assert "Sortable" in js
    assert "threshold" in js
    assert "/save" in js
    assert "session_seconds" in js or "secondsLeft" in js


def test_css_has_domain_classes():
    css = (FRONTEND_DIR / "cluster.css").read_text()
    assert ".own-domain" in css
    assert ".competitor" in css
    assert ".authority" in css or "authority" in css

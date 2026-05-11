from seo_toolbox.grouping import greedy_volume_clustering


def test_single_keyword_makes_single_cluster():
    result = greedy_volume_clustering(
        keywords=["a"],
        volumes={"a": 100},
        similarity_matrix={"a": {"a": 1.0}},
        threshold=0.3,
    )
    assert len(result.clusters) == 1
    assert result.clusters[0].primary == "a"
    assert result.clusters[0].members == ["a"]
    assert result.ungrouped == []


def test_high_overlap_keywords_cluster_together():
    matrix = {
        "SEO 工具": {"SEO 工具": 1.0, "SEO 關鍵字工具": 0.8, "GEO 在地搜尋": 0.0},
        "SEO 關鍵字工具": {"SEO 工具": 0.8, "SEO 關鍵字工具": 1.0, "GEO 在地搜尋": 0.0},
        "GEO 在地搜尋": {"SEO 工具": 0.0, "SEO 關鍵字工具": 0.0, "GEO 在地搜尋": 1.0},
    }
    result = greedy_volume_clustering(
        keywords=["SEO 工具", "SEO 關鍵字工具", "GEO 在地搜尋"],
        volumes={"SEO 工具": 1000, "SEO 關鍵字工具": 500, "GEO 在地搜尋": 200},
        similarity_matrix=matrix,
        threshold=0.3,
    )
    assert len(result.clusters) == 2
    seo_cluster = next(c for c in result.clusters if "SEO 工具" in c.members)
    assert "SEO 關鍵字工具" in seo_cluster.members
    assert seo_cluster.primary == "SEO 工具"


def test_below_threshold_does_not_cluster():
    matrix = {
        "a": {"a": 1.0, "b": 0.2},
        "b": {"a": 0.2, "b": 1.0},
    }
    result = greedy_volume_clustering(
        keywords=["a", "b"],
        volumes={"a": 100, "b": 50},
        similarity_matrix=matrix,
        threshold=0.3,
    )
    assert len(result.clusters) == 2  # both become their own primary


def test_higher_volume_keyword_becomes_primary():
    matrix = {
        "low": {"low": 1.0, "high": 0.9},
        "high": {"low": 0.9, "high": 1.0},
    }
    result = greedy_volume_clustering(
        keywords=["low", "high"],
        volumes={"low": 50, "high": 500},
        similarity_matrix=matrix,
        threshold=0.3,
    )
    assert len(result.clusters) == 1
    assert result.clusters[0].primary == "high"
    assert "low" in result.clusters[0].members


def test_zero_volume_keywords_handled():
    matrix = {"a": {"a": 1.0, "b": 0.5}, "b": {"a": 0.5, "b": 1.0}}
    result = greedy_volume_clustering(
        keywords=["a", "b"],
        volumes={},  # all zero
        similarity_matrix=matrix,
        threshold=0.3,
    )
    assert len(result.clusters) >= 1  # deterministic ordering, no crash


def test_higher_volume_member_not_absorbed():
    """A higher-volume keyword encountered later must NOT be absorbed by a
    lower-volume primary — it should become its own primary."""
    matrix = {
        "low": {"low": 1.0, "high": 0.9},
        "high": {"low": 0.9, "high": 1.0},
    }
    result = greedy_volume_clustering(
        keywords=["low", "high"],
        volumes={"low": 100, "high": 200},
        similarity_matrix=matrix,
        threshold=0.3,
    )
    # "high" has higher volume than "low", so even though we pass them in
    # this order, sorting puts "high" first → "high" becomes primary, "low" attaches.
    # If sorted differently, "high" must NOT be absorbed under "low" (vol guard).
    high_cluster = next(c for c in result.clusters if c.primary == "high")
    assert "low" in high_cluster.members
    assert all(c.primary != "low" for c in result.clusters)

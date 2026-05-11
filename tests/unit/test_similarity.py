from seo_toolbox.similarity import jaccard, percentage, shared_count


# Jaccard
def test_jaccard_identical_sets_returns_one():
    s = {"a", "b", "c"}
    assert jaccard(s, s) == 1.0


def test_jaccard_disjoint_sets_returns_zero():
    assert jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_partial_overlap():
    # 4 shared / 16 union = 0.25
    a = {"u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8", "u9", "u10"}
    b = {"u1", "u2", "u3", "u4", "u11", "u12", "u13", "u14", "u15", "u16"}
    assert jaccard(a, b) == 0.25


def test_jaccard_empty_returns_zero():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a"}, set()) == 0.0
    assert jaccard(set(), set()) == 0.0


def test_jaccard_is_symmetric():
    a = {"a", "b", "c"}
    b = {"b", "c", "d"}
    assert jaccard(a, b) == jaccard(b, a)


# Percentage (overlap coefficient)
def test_percentage_full_containment_returns_one():
    a = {"a", "b", "c", "d", "e"}
    b = {"a", "b", "c"}
    assert percentage(a, b) == 1.0


def test_percentage_disjoint_returns_zero():
    assert percentage({"a"}, {"b"}) == 0.0


def test_percentage_uses_smaller_set_size():
    # 4 shared, smaller=5, so 4/5
    a = {"u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8", "u9", "u10"}
    b = {"u1", "u2", "u3", "u4", "u11"}
    assert percentage(a, b) == 0.8


def test_percentage_empty_returns_zero():
    assert percentage(set(), {"a"}) == 0.0
    assert percentage({"a"}, set()) == 0.0
    assert percentage(set(), set()) == 0.0


# Shared count
def test_shared_count_returns_int():
    assert shared_count({"a", "b", "c"}, {"b", "c", "d"}) == 2


def test_shared_count_empty():
    assert shared_count(set(), {"a"}) == 0

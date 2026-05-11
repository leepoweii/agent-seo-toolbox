"""Set-based similarity metrics for SERP URL comparison."""
from __future__ import annotations


def shared_count(a: set[str], b: set[str]) -> int:
    """Count of URLs present in both sets. Range: 0 to min(len(a), len(b))."""
    return len(a & b)


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|. Range 0.0–1.0. Returns 0.0 if either set is empty."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def percentage(a: set[str], b: set[str]) -> float:
    """Szymkiewicz–Simpson overlap coefficient: |A ∩ B| / min(|A|, |B|).

    Range 0.0–1.0 (NOT a percentage from 0 to 100, despite the function name).
    Equals 1.0 when one set is fully contained in the other.
    Returns 0.0 if either set is empty.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))

"""Volume-anchored greedy keyword clustering.

Mirrors greedyVolumeGrouping in simple-seo-tools/apps/web-v2/src/lib/grouping.ts.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cluster:
    primary: str  # head term — highest-volume keyword in the cluster
    members: list[str] = field(default_factory=list)  # includes primary
    volume: int = 0  # sum of all members' volumes (including primary)


@dataclass
class GroupingResult:
    clusters: list[Cluster]
    # Always [] given current algorithm — every keyword becomes either primary
    # or member. Reserved for future extensions (max cluster size, exclusion list).
    ungrouped: list[str]


def greedy_volume_clustering(
    keywords: list[str],
    volumes: dict[str, int],
    similarity_matrix: dict[str, dict[str, float]],
    threshold: float,
) -> GroupingResult:
    """Volume-sorted greedy clustering. Highest-volume becomes primary.

    Algorithm:
      1. Sort keywords by volume descending (stable for ties).
      2. For each unassigned keyword, designate as primary; walk remaining
         unassigned, attach if similarity(primary, kw) >= threshold AND
         kw.volume <= primary.volume.
      3. With the current algorithm, every keyword ends up in a cluster (`ungrouped`
         is always `[]`). The field is preserved for future extensions.
    """
    sorted_kws = sorted(keywords, key=lambda k: (-volumes.get(k, 0), k))
    assigned: set[str] = set()
    clusters: list[Cluster] = []

    for primary in sorted_kws:
        if primary in assigned:
            continue
        primary_vol = volumes.get(primary, 0)
        cluster = Cluster(primary=primary, members=[primary], volume=primary_vol)
        assigned.add(primary)

        for kw in sorted_kws:
            if kw in assigned:
                continue
            # Symmetric lookup: caller may provide a half-filled matrix
            sim = (
                similarity_matrix.get(primary, {}).get(kw)
                or similarity_matrix.get(kw, {}).get(primary, 0.0)
            )
            if sim < threshold:
                continue
            kw_vol = volumes.get(kw, 0)
            if kw_vol > primary_vol:
                continue
            cluster.members.append(kw)
            cluster.volume += kw_vol
            assigned.add(kw)

        clusters.append(cluster)

    ungrouped = [k for k in keywords if k not in assigned]
    return GroupingResult(clusters=clusters, ungrouped=ungrouped)

// cluster-graph.js — D3 force-directed graph view (visual-only, explorer layout)
// Reads same payload as cluster.js; exposes window.ClusterGraph API
// Sync: explorer drag-drop / threshold → ClusterGraph.refresh(clusters, ungrouped, threshold)
//       graph node click              → window._selectKw(kw)
//       explorer row click            → window._graphHighlight(kw)
(function () {
  const payload = JSON.parse(document.getElementById("payload").textContent);
  const keywords  = payload.keywords;
  const volumes   = payload.volumes;
  const serps     = payload.serps;
  const jaccard   = payload.jaccard;
  const domains   = payload.domains;

  function getSharedCount(a, b) {
    const setA = new Set((serps[a] || []).map(u => u.replace(/^https?:\/\/(www\.)?/, "")));
    return (serps[b] || []).filter(u => setA.has(u.replace(/^https?:\/\/(www\.)?/, ""))).length;
  }

  function fmtVol(n) { return Number(n || 0).toLocaleString(); }

  const CLUSTER_COLORS = [
    "#C0603A","#3A7DC0","#3A9E5A","#9E3AB0","#C0962A",
    "#2AABBF","#B03A5C","#5C8C3A","#A06030","#4A5CAE",
  ];
  const UNGROUPED   = "#9CA3AF";
  const OWN_COLOR   = "#0EA472";
  const AUTH_COLOR  = "#F59E0B";
  const COMP_COLOR  = "#E94B7D";
  const LINK_COLOR  = "#C8BAA0";

  let simulation   = null;
  let activeNodeId = null;

  // ── helpers ────────────────────────────────────────────────
  function urlKlass(url) {
    if (!url) return "";
    const host = url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];
    if (domains.own && host.endsWith(domains.own)) return "own";
    if ((domains.competitors || []).some(c => host.endsWith(c))) return "competitor";
    if ((domains.authority_tlds || []).some(t => host.endsWith(t))) return "authority";
    return "";
  }

  function badges() {
    const out = {};
    for (const kw of keywords) {
      let auth = 0, comp = 0, own = 0;
      for (const u of (serps[kw] || [])) {
        const c = urlKlass(u);
        if (c === "own") own++;
        else if (c === "authority") auth++;
        else if (c === "competitor") comp++;
      }
      out[kw] = { auth, comp, own };
    }
    return out;
  }

  function sizeOf(vol, scale) {
    return scale(Math.max(1, vol || 0));
  }

  function truncate(s, r) {
    const max = Math.max(2, Math.floor(r / 2.8));
    return s.length > max ? s.slice(0, max) + "…" : s;
  }

  // ── graph build ─────────────────────────────────────────────
  function buildGraph(clusters, ungrouped, threshold) {
    const container = document.getElementById("graph-pane");
    if (!container) return;
    container.innerHTML = "";
    if (simulation) { simulation.stop(); simulation = null; }
    activeNodeId = null;

    // ── data ──
    const badge = badges();
    const kwColor = new Map();
    clusters.forEach((c, i) => c.members.forEach(kw =>
      kwColor.set(kw, CLUSTER_COLORS[i % CLUSTER_COLORS.length])));
    ungrouped.forEach(kw => kwColor.set(kw, UNGROUPED));

    const nodes = keywords.map(kw => ({
      id:    kw,
      vol:   volumes[kw] || 0,
      badge: badge[kw] || { auth: 0, comp: 0, own: false },
      color: kwColor.get(kw) || UNGROUPED,
    }));

    const seen = new Set();
    const links = [];
    for (const src of keywords) {
      for (const [tgt, ov] of Object.entries(jaccard[src] || {})) {
        if (ov < threshold) continue;
        const key = src < tgt ? `${src}|${tgt}` : `${tgt}|${src}`;
        if (seen.has(key)) continue;
        seen.add(key);
        links.push({ source: src, target: tgt, overlap: ov, count: getSharedCount(src, tgt) });
      }
    }

    const connectedIds = new Set(links.flatMap(l => [l.source, l.target]));

    // ── svg dimensions (defined before pre-positioning) ──
    const W = container.clientWidth  || 900;
    const H = container.clientHeight || 560;

    // Pre-position isolated nodes near center so radial force converges fast
    nodes.forEach(n => {
      if (!connectedIds.has(n.id)) {
        n.x = W / 2 + (Math.random() - 0.5) * 140;
        n.y = H / 2 + (Math.random() - 0.5) * 140;
      }
    });

    // ── scales ──
    const maxVol = Math.max(...nodes.map(n => n.vol), 1);
    const minVol = Math.max(1, Math.min(...nodes.map(n => n.vol).filter(v => v > 0), maxVol));
    const sz = d3.scaleLog().domain([minVol, Math.max(maxVol, minVol + 1)]).range([7, 46]).clamp(true);
    const maxOv = Math.max(...links.map(l => l.overlap), threshold + 0.01);
    const lw = d3.scaleLinear().domain([threshold, maxOv]).range([1.5, 5]).clamp(true);

    // ── svg ──
    const root = d3.select(container).append("svg")
      .attr("width", "100%").attr("height", "100%")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .style("background", "transparent");

    const zoom = d3.zoom().scaleExtent([0.1, 4]).on("zoom", e => g.attr("transform", e.transform));
    root.call(zoom);

    const g = root.append("g");

    // ── links ──
    const link = g.append("g").attr("class", "links").selectAll("line")
      .data(links).join("line")
      .attr("stroke", LINK_COLOR)
      .attr("stroke-opacity", 0.55)
      .attr("stroke-width", d => lw(d.overlap));

    // edge overlap count labels (shown on hover)
    const linkLabel = g.append("g").attr("class", "link-labels").selectAll("text")
      .data(links).join("text")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .attr("pointer-events", "none")
      .attr("fill", "#FB923C")
      .attr("stroke", "#fff")
      .attr("stroke-width", "3px")
      .attr("paint-order", "stroke fill")
      .attr("opacity", 0)
      .style("font-size", "12px")
      .style("font-family", "var(--mono)")
      .style("font-weight", "800")
      .text(d => d.count);

    // ── nodes ──
    const nodeG = g.append("g").attr("class", "nodes").selectAll("g")
      .data(nodes).join("g")
      .attr("class", "g-node")
      .style("cursor", "pointer")
      .call(d3.drag()
        .on("start", (ev, d) => {
          if (!ev.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
        .on("end",   (ev, d) => {
          if (!ev.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        }));

    // circles
    nodeG.append("circle").attr("class", "nc")
      .attr("r",    d => sizeOf(d.vol, sz))
      .attr("fill", d => d.color)
      .attr("stroke", "#fff")
      .attr("stroke-width", 2)
      .attr("opacity", d => connectedIds.has(d.id) ? 0.88 : 0.45);

    // badge dots
    nodeG.each(function(d) {
      const r    = sizeOf(d.vol, sz);
      const dotR = 3.5;
      [
        { n: Math.min(d.badge.own,  4), color: OWN_COLOR,  arcStart:  Math.PI * 0.75, arcSpan: Math.PI * 0.4 },
        { n: Math.min(d.badge.auth, 8), color: AUTH_COLOR, arcStart: -Math.PI * 0.75, arcSpan: Math.PI * 0.5 },
        { n: Math.min(d.badge.comp, 8), color: COMP_COLOR, arcStart:  Math.PI * 0.25, arcSpan: Math.PI * 0.5 },
      ].forEach(({ n, color, arcStart, arcSpan }) => {
        for (let i = 0; i < n; i++) {
          const a = arcStart + (n > 1 ? (i / (n - 1)) * arcSpan : arcSpan / 2);
          d3.select(this).append("circle")
            .attr("r", dotR)
            .attr("cx", Math.cos(a) * (r + 2))
            .attr("cy", Math.sin(a) * (r + 2))
            .attr("fill", color).attr("stroke", "#fff").attr("stroke-width", 1)
            .attr("pointer-events", "none");
        }
      });
    });

    // inner label
    nodeG.append("text").attr("class", "nl-in")
      .attr("text-anchor", "middle").attr("dominant-baseline", "central")
      .attr("pointer-events", "none").attr("fill", "#fff")
      .style("font-size", d => Math.max(7, sizeOf(d.vol, sz) * 0.28) + "px")
      .style("font-weight", "600").style("font-family", "var(--sans)")
      .text(d => truncate(d.id, sizeOf(d.vol, sz)));

    // outer label (shown on hover / selection)
    nodeG.append("text").attr("class", "nl-out")
      .attr("text-anchor", "middle")
      .attr("dy", d => sizeOf(d.vol, sz) + 14)
      .attr("pointer-events", "none")
      .attr("fill", "var(--ink-2)")
      .attr("opacity", 0)
      .style("font-size", "10px").style("font-family", "var(--sans)")
      .text(d => d.id.length > 18 ? d.id.slice(0, 17) + "…" : d.id);

    // ── regular highlight (single-click) ────────────────────
    function updateHL(nodeId) {
      activeNodeId = nodeId;
      if (!nodeId) {
        nodeG.select("circle.nc")
          .attr("opacity", d => connectedIds.has(d.id) ? 0.88 : 0.45)
          .attr("fill",    d => d.color)
          .attr("stroke",  "#fff").attr("stroke-width", 2);
        nodeG.select(".nl-out").attr("opacity", 0);
        nodeG.select(".nl-in").text(d => truncate(d.id, sizeOf(d.vol, sz)));
        link.attr("stroke", LINK_COLOR).attr("stroke-opacity", 0.55);
        linkLabel.attr("opacity", 0);
        return;
      }

      const connected = new Set([nodeId]);
      for (const [t, ov] of Object.entries(jaccard[nodeId] || {}))
        if (ov >= threshold) connected.add(t);
      for (const kw of keywords)
        if ((jaccard[kw]?.[nodeId] ?? 0) >= threshold) connected.add(kw);

      const activeVol = volumes[nodeId] || 0;

      nodeG.select("circle.nc")
        .attr("opacity", d => d.id === nodeId ? 1 : connected.has(d.id) ? 0.85 : 0.28)
        .attr("fill", d => {
          if (d.id === nodeId || !connected.has(d.id)) return d.color;
          return (volumes[d.id] || 0) > activeVol ? "#EAD9A2" : "#FB923C";
        })
        .attr("stroke",       d => connected.has(d.id) ? "#fff" : "#bbb")
        .attr("stroke-width", d => d.id === nodeId ? 3 : 2);

      nodeG.select(".nl-out").attr("opacity", d => connected.has(d.id) ? 1 : 0);

      // show volume inside all lit nodes
      nodeG.select(".nl-in").text(d => connected.has(d.id) ? fmtVol(d.vol) : truncate(d.id, sizeOf(d.vol, sz)));

      link.attr("stroke", d => {
        const s = d.source.id ?? d.source;
        const t = d.target.id ?? d.target;
        return (s === nodeId || t === nodeId) ? "#FB923C" : LINK_COLOR;
      }).attr("stroke-opacity", d => {
        const s = d.source.id ?? d.source;
        const t = d.target.id ?? d.target;
        return (s === nodeId || t === nodeId) ? 0.85 : 0.04;
      });

      // show overlap count on incident edges
      linkLabel.attr("opacity", d => {
        const s = d.source.id ?? d.source;
        const t = d.target.id ?? d.target;
        return (s === nodeId || t === nodeId) ? 1 : 0;
      });
    }

    window._graphHighlight = updateHL;

    // ── event handlers ───────────────────────────────────────
    root.on("click", () => {
      updateHL(null);
      if (window._selectKw) window._selectKw(null);
    });

    nodeG
      .on("mouseenter", (ev, d) => {
        if (activeNodeId) return;
        updateHL(d.id);
        ev.stopPropagation();
      })
      .on("mouseleave", (ev, d) => {
        if (activeNodeId === d.id) return;
        updateHL(null);
      })
      .on("click", (ev, d) => {
        ev.stopPropagation();
        const next = activeNodeId === d.id ? null : d.id;
        updateHL(next);
        if (window._selectKw) window._selectKw(next);
      });

    // ── fit-to-bounds button ──────────────────────────────────
    d3.select(container).append("button")
      .attr("class", "graph-fit-btn")
      .text("⊡ Fit")
      .on("click", () => {
        root.transition().duration(400).call(
          zoom.transform,
          d3.zoomIdentity.translate(W / 2, H / 2).scale(0.85)
        );
      });

    // ── simulation ───────────────────────────────────────────
    simulation = d3.forceSimulation(nodes)
      .force("link",    d3.forceLink(links).id(d => d.id).distance(80).strength(0.6))
      .force("charge",  d3.forceManyBody()
        .strength(d => connectedIds.has(d.id) ? -180 : -20))
      .force("center",  d3.forceCenter(W / 2, H / 2))
      .force("collide", d3.forceCollide()
        .radius(d => sizeOf(d.vol, sz) + (connectedIds.has(d.id) ? 9 : 4)))
      .force("radial",  d3.forceRadial(60, W / 2, H / 2)
        .strength(d => connectedIds.has(d.id) ? 0 : 0.9));

    simulation.on("tick", () => {
      link
        .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
      linkLabel
        .attr("x", d => ((d.source.x ?? 0) + (d.target.x ?? 0)) / 2)
        .attr("y", d => ((d.source.y ?? 0) + (d.target.y ?? 0)) / 2);
      nodeG.attr("transform", d => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });
  }

  // ── Public API ───────────────────────────────────────────────
  window.ClusterGraph = {
    init(clusters, ungrouped, threshold) {
      buildGraph(clusters, ungrouped, threshold);
    },
    refresh(clusters, ungrouped, threshold) {
      buildGraph(clusters, ungrouped, threshold);
    },
    destroy() {
      if (simulation) { simulation.stop(); simulation = null; }
      const c = document.getElementById("graph-pane");
      if (c) c.innerHTML = "";
      window._graphHighlight = null;
    },
  };

  // Auto-init: cluster.js sets window.__clusterState before this script runs.
  // One rAF gives the browser time to lay out graph-pane so clientWidth/Height are valid.
  requestAnimationFrame(() => {
    const state = window.__clusterState;
    if (state) buildGraph(state.clusters, state.ungrouped, state.threshold);
  });
})();

// cluster-polished.js — drop-in replacement for cluster.js
// Change from original: each explorer folder gets --folder-color CSS custom
// property so the left-border accent matches the D3 graph node color.
(function () {
  const payload = JSON.parse(document.getElementById("payload").textContent);
  const keywords = payload.keywords;
  const volumes = payload.volumes;
  const serps = payload.serps;
  const serpFeatures = payload.serp_features || {};
  const jaccard = payload.jaccard;
  const domains = payload.domains;

  let clusters = JSON.parse(JSON.stringify(payload.initial_clusters));
  let ungrouped = [...payload.ungrouped];
  let threshold = parseFloat(document.getElementById("threshold").value);

  // Cluster palette — must match cluster-graph-polished.js
  const CLUSTER_COLORS = [
    "#C0603A","#3A7DC0","#3A9E5A","#9E3AB0","#C0962A",
    "#2AABBF","#B03A5C","#5C8C3A","#A06030","#4A5CAE",
  ];

  // ----- helpers -----
  function fmtInt(n) { return Number(n || 0).toLocaleString(); }
  function pad2(n)   { return String(n).padStart(2, "0"); }

  function normalizeUrl(u) {
    if (!u) return "";
    return u.replace(/^https?:\/\/(www\.)?/, "");
  }

  function urlClass(url) {
    if (!url) return "";
    const host = normalizeUrl(url).split("/")[0];
    if (domains.own && host.endsWith(domains.own)) return "own-domain";
    if ((domains.competitors || []).some(c => host.endsWith(c))) return "competitor";
    if ((domains.authority_tlds || []).some(t => host.endsWith(t))) return "authority";
    return "";
  }

  function shortenUrl(url) { return normalizeUrl(url); }

  // ----- threshold slider fill -----
  const sliderEl = document.getElementById("threshold");
  function updateSliderFill() {
    const pct = Math.round(parseFloat(sliderEl.value) * 100);
    sliderEl.style.setProperty("--filled", pct + "%");
  }
  updateSliderFill();

  // ----- render -----
  function makeKwRow(kw, primary) {
    const row = document.createElement("div");
    row.className = "kw-row";
    row.dataset.kw = kw;

    const head = document.createElement("div");
    head.className = "kw-header";

    const kwSpan = document.createElement("span");
    kwSpan.className = "kw-text";
    kwSpan.textContent = kw;
    head.appendChild(kwSpan);

    appendOverlapBadges(head, kw, primary, "primary");

    const volSpan = document.createElement("span");
    volSpan.className = "kw-vol";
    volSpan.textContent = fmtInt(volumes[kw] || 0);
    head.appendChild(volSpan);

    row.appendChild(head);
    if (primary && primary !== kw) row.dataset.primary = primary;
    return row;
  }

  function appendOverlapBadges(headEl, kw, comparedTo, label) {
    if (!comparedTo || comparedTo === kw) return;
    const kwUrls  = new Set((serps[kw] || []).map(normalizeUrl));
    const otherUrls = (serps[comparedTo] || []).map(normalizeUrl);
    const overlap   = otherUrls.filter(u => kwUrls.has(u));
    const overlapOrig = (serps[kw] || []).filter(u => overlap.includes(normalizeUrl(u)));
    let nOwn = 0, nComp = 0, nAuth = 0;
    overlapOrig.forEach(u => {
      const c = urlClass(u);
      if (c === "own-domain")  nOwn++;
      else if (c === "competitor") nComp++;
      else if (c === "authority")  nAuth++;
    });

    const ovSpan = document.createElement("span");
    ovSpan.className = "kw-overlap";
    ovSpan.textContent = String(overlap.length);
    ovSpan.title = `${overlap.length} of 10 URLs shared with ${label} (${comparedTo})`;
    headEl.appendChild(ovSpan);

    [["own-domain", nOwn], ["authority", nAuth], ["competitor", nComp]].forEach(([cls, n]) => {
      if (!n) return;
      const b = document.createElement("span");
      b.className = `kw-pill ${cls}`;
      b.textContent = n;
      b.title = `${n} ${cls} URL${n > 1 ? "s" : ""} in overlap`;
      headEl.appendChild(b);
    });
  }

  function recomputeRowBadges(row, comparedTo, label) {
    const head = row.querySelector(".kw-header");
    if (!head) return;
    head.querySelectorAll(".kw-overlap, .kw-pill").forEach(el => el.remove());
    const kw = row.dataset.kw;
    const volSpan = head.querySelector(".kw-vol");
    const tmpDiv = document.createElement("div");
    appendOverlapBadges(tmpDiv, kw, comparedTo, label);
    Array.from(tmpDiv.children).forEach(child => head.insertBefore(child, volSpan));
  }

  // ----- sidebar -----
  let selectedKw = null;

  function faviconFor(domainOrUrl) {
    const d = normalizeUrl(domainOrUrl).split("/")[0];
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(d)}&sz=32`;
  }

  function renderMarkdown(md) {
    if (!md) return "";
    if (typeof marked !== "undefined") return marked.parse(md, { breaks: true, gfm: true });
    return md
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\n/g, "<br>");
  }

  function renderSidebar(kw) {
    const sidebar = document.getElementById("sidebar");
    if (!kw) {
      sidebar.innerHTML = `
        <div class="sidebar-empty">
          <div class="eyebrow"><span>SIDEBAR</span></div>
          <p class="lede">Click any keyword to see its SERP — AI Overview, Featured Snippet, People Also Ask, and the top-10 organic with overlap highlighted.</p>
        </div>`;
      return;
    }
    let primary = null;
    for (const c of clusters) {
      if (c.members.includes(kw)) { primary = c.primary; break; }
    }
    const isPrimary = primary === kw;
    const features  = serpFeatures[kw] || {};
    const organic   = features.organic || [];
    const primaryUrlSet = (primary && primary !== kw)
      ? new Set((serps[primary] || []).map(normalizeUrl))
      : null;

    sidebar.innerHTML = "";

    const head = document.createElement("div");
    head.className = "sidebar-head";
    head.innerHTML = `
      <div class="sidebar-meta">
        <span class="sidebar-vol">${fmtInt(volumes[kw] || 0)}</span>
        <span class="sidebar-vs">${
          isPrimary ? "primary"
          : (primary ? `vs <em>${escapeHtml(primary)}</em>` : "ungrouped")
        }</span>
      </div>`;
    sidebar.appendChild(head);

    // AI Overview
    if (features.ai_overview && features.ai_overview.markdown) {
      const refs = features.ai_overview.references || [];
      const sec  = document.createElement("section");
      sec.className = "sidebar-section ai-overview";
      const aiDetails = document.createElement("details");
      aiDetails.className = "collapsible";
      aiDetails.innerHTML = `
        <summary><span class="ai-badge">AI Overview</span><span class="chev"></span></summary>
        <div class="ai-md">${renderMarkdown(features.ai_overview.markdown)}</div>`;
      sec.appendChild(aiDetails);

      if (refs.length) {
        const refDetails = document.createElement("details");
        refDetails.className = "collapsible ai-refs-collapsible";
        const sum = document.createElement("summary");
        sum.innerHTML = `<span class="collapsible-label">Sources <span class="count">(${refs.length})</span></span><span class="chev"></span>`;
        refDetails.appendChild(sum);
        const list = document.createElement("div");
        list.className = "ai-refs-list";
        refs.slice(0, 10).forEach(r => {
          const u = r.url || "";
          if (!u) return;
          const a = document.createElement("a");
          a.className = "ai-ref";
          a.href = u; a.target = "_blank"; a.rel = "noopener noreferrer";
          const cls = urlClass(u);
          if (cls) a.classList.add(cls);
          if (primaryUrlSet && primaryUrlSet.has(normalizeUrl(u))) a.classList.add("overlap-with-primary");
          a.innerHTML = `<img class="favicon" src="${faviconFor(u)}" loading="lazy" onerror="this.style.visibility='hidden'"><span class="ai-ref-title">${escapeHtml(r.title || shortenUrl(u))}</span>`;
          list.appendChild(a);
        });
        refDetails.appendChild(list);
        sec.appendChild(refDetails);
      }
      sidebar.appendChild(sec);
    }

    // Featured Snippet
    if (features.featured_snippet) {
      const fs  = features.featured_snippet;
      const sec = document.createElement("section");
      sec.className = "sidebar-section";
      sec.appendChild(makeSerpResult({
        url: fs.url, title: fs.title, description: fs.description,
        domain: fs.url ? normalizeUrl(fs.url).split("/")[0] : "",
      }, null, primaryUrlSet, "featured"));
      sidebar.appendChild(sec);
    }

    // PAA
    if ((features.paa || []).length) {
      const sec = document.createElement("section");
      sec.className = "sidebar-section paa-section";
      const det = document.createElement("details");
      det.className = "collapsible";
      const sum = document.createElement("summary");
      sum.innerHTML = `<span class="collapsible-label paa-head">People also ask <span class="count">(${features.paa.length})</span></span><span class="chev"></span>`;
      det.appendChild(sum);
      const list = document.createElement("div");
      list.className = "paa-list";
      features.paa.slice(0, 8).forEach(q => {
        const item = document.createElement("div");
        item.className = "paa-item";
        item.textContent = q.title || q.text || "";
        list.appendChild(item);
      });
      det.appendChild(list);
      sec.appendChild(det);
      sidebar.appendChild(sec);
    }

    // Organic
    const sec = document.createElement("section");
    sec.className = "sidebar-section organic-section";
    if (organic.length) {
      organic.forEach((r, i) => sec.appendChild(makeSerpResult(r, i + 1, primaryUrlSet, null)));
    } else {
      (serps[kw] || []).slice(0, 10).forEach((u, i) => {
        sec.appendChild(makeSerpResult({ url: u, domain: normalizeUrl(u).split("/")[0], title: shortenUrl(u) }, i + 1, primaryUrlSet, null));
      });
    }
    sidebar.appendChild(sec);
  }

  function makeSerpResult(r, rank, primaryUrlSet, badge) {
    const a = document.createElement("a");
    a.className = "serp-result";
    a.href = r.url || "#"; a.target = "_blank"; a.rel = "noopener noreferrer";
    const cls = urlClass(r.url);
    if (cls) a.classList.add(cls);
    if (primaryUrlSet && r.url && primaryUrlSet.has(normalizeUrl(r.url))) a.classList.add("overlap-with-primary");

    const head = document.createElement("div");
    head.className = "serp-result-head";
    const fav = document.createElement("img");
    fav.className = "favicon";
    fav.src = faviconFor(r.url || r.domain);
    fav.loading = "lazy";
    fav.onerror = function () { this.style.visibility = "hidden"; };
    head.appendChild(fav);

    const meta = document.createElement("div");
    meta.className = "serp-result-meta";
    const dom = document.createElement("div");
    dom.className = "serp-domain";
    dom.textContent = r.domain || (r.url ? normalizeUrl(r.url).split("/")[0] : "");
    meta.appendChild(dom);
    const path = document.createElement("div");
    path.className = "serp-path";
    path.textContent = r.url ? shortenUrl(r.url) : "";
    meta.appendChild(path);
    head.appendChild(meta);

    if (rank) {
      const rk = document.createElement("span");
      rk.className = "serp-rank";
      rk.textContent = rank;
      head.appendChild(rk);
    }
    if (badge === "featured") {
      const b = document.createElement("span");
      b.className = "serp-badge featured";
      b.textContent = "Featured";
      head.appendChild(b);
    }
    a.appendChild(head);

    const title = document.createElement("h3");
    title.className = "serp-title";
    title.textContent = r.title || "";
    a.appendChild(title);

    if (r.description) {
      const desc = document.createElement("p");
      desc.className = "serp-desc";
      desc.textContent = r.description;
      a.appendChild(desc);
    }
    return a;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  }

  function selectKw(kw) {
    selectedKw = kw;
    document.querySelectorAll(".kw-row.selected").forEach(r => r.classList.remove("selected"));
    if (kw) {
      const row = document.querySelector(`.kw-row[data-kw="${CSS.escape(kw)}"]`);
      if (row) {
        row.classList.add("selected");
        const folder = row.closest(".ex-folder");
        if (folder && !folder.classList.contains("open")) folder.classList.add("open");
        // Use scrollTop instead of scrollIntoView to avoid messing up the app
        const panel = document.getElementById("explorer");
        if (panel) {
          const rowTop    = row.offsetTop;
          const panelTop  = panel.scrollTop;
          const panelBot  = panelTop + panel.clientHeight;
          if (rowTop < panelTop || rowTop + row.offsetHeight > panelBot) {
            panel.scrollTop = rowTop - 60;
          }
        }
      }
    }
    renderSidebar(kw);
    if (window._graphHighlight) window._graphHighlight(kw);
  }

  window._selectKw = selectKw;

  window._createGroupFromGraph = function(kwSet) {
    const kws = [...kwSet];
    kws.forEach(kw => {
      clusters.forEach(c => { c.members = c.members.filter(m => m !== kw); });
      ungrouped = ungrouped.filter(u => u !== kw);
    });
    const primary = kws.reduce((a, b) => (volumes[a]||0) >= (volumes[b]||0) ? a : b);
    const newCluster = { primary, members: kws, volume: kws.reduce((s, k) => s + (volumes[k]||0), 0) };
    clusters.push(newCluster);
    clusters = clusters
      .filter(c => c.members.length > 0)
      .map(c => ({
        ...c,
        primary: c.members.reduce((a, b) => (volumes[a]||0) >= (volumes[b]||0) ? a : b),
        volume:  c.members.reduce((s, k) => s + (volumes[k]||0), 0),
      }));
    render();
    if (window.ClusterGraph) window.ClusterGraph.refresh(clusters, ungrouped, threshold);
    selectKw(primary);
  };

  document.getElementById("explorer").addEventListener("click", e => {
    const row = e.target.closest(".kw-row");
    if (!row) return;
    selectKw(row.dataset.kw);
  });

  // ----- hover-highlight -----
  let hoveredKw   = null;
  let isDragging  = false;

  function applyHoverState(targetKw) {
    document.querySelectorAll(".kw-row").forEach(row => {
      const kw = row.dataset.kw;
      row.classList.remove("hover-self", "hover-related", "hover-dim");
      if (!targetKw) {
        recomputeRowBadges(row, row.dataset.primary || null, "primary");
        return;
      }
      if (kw === targetKw) {
        row.classList.add("hover-self");
        recomputeRowBadges(row, null, "");
        return;
      }
      const ov = (jaccard[targetKw]?.[kw]) ?? (jaccard[kw]?.[targetKw]) ?? 0;
      row.classList.add(ov >= threshold ? "hover-related" : "hover-dim");
      recomputeRowBadges(row, targetKw, "hovered");
    });
  }

  const explorerEl = document.getElementById("explorer");
  explorerEl.addEventListener("mouseover", e => {
    if (isDragging) return;
    const row = e.target.closest(".kw-row");
    if (!row) return;
    const kw = row.dataset.kw;
    if (kw === hoveredKw) return;
    hoveredKw = kw;
    applyHoverState(kw);
  });
  explorerEl.addEventListener("mouseleave", () => {
    if (hoveredKw === null) return;
    hoveredKw = null;
    applyHoverState(null);
  });

  // ── Explorer folder builders ──────────────────────────────

  function buildExplorerFolder(c, ci) {
    const sec = document.createElement("section");
    sec.className = "cluster ex-folder open";
    sec.dataset.clusterIdx = String(ci);
    // ★ cluster color accent — key polished addition
    sec.style.setProperty("--folder-color", CLUSTER_COLORS[ci % CLUSTER_COLORS.length]);

    const hd = document.createElement("div");
    hd.className = "ex-folder-hd";
    hd.innerHTML = `
      <span class="ex-chev">▶</span>
      <span class="ex-number">${escapeHtml(pad2(ci + 1))}</span>
      <span class="ex-name" title="${escapeHtml(c.primary)}">${escapeHtml(c.primary)}</span>
      <span class="ex-badge">${c.members.length} kw</span>
      <span class="ex-vol">${fmtInt(c.volume || 0)}</span>`;
    hd.addEventListener("click", () => sec.classList.toggle("open"));
    sec.appendChild(hd);

    const body = document.createElement("div");
    body.className = "ex-folder-body";
    c.members.forEach(kw => body.appendChild(makeKwRow(kw, c.primary)));
    sec.appendChild(body);
    return sec;
  }

  function buildExplorerUngrouped() {
    const sec = document.createElement("section");
    sec.className = "cluster ungrouped ex-folder open";
    sec.dataset.clusterIdx = "ungrouped";
    const hd = document.createElement("div");
    hd.className = "ex-folder-hd";
    hd.innerHTML = `
      <span class="ex-chev">▶</span>
      <span class="ex-name ex-name-ungrouped">Ungrouped</span>
      <span class="ex-badge">${ungrouped.length} kw</span>`;
    hd.addEventListener("click", () => sec.classList.toggle("open"));
    sec.appendChild(hd);
    const body = document.createElement("div");
    body.className = "ex-folder-body";
    ungrouped.forEach(kw => body.appendChild(makeKwRow(kw, null)));
    sec.appendChild(body);
    return sec;
  }

  function buildExplorerNewSlot() {
    const sec = document.createElement("section");
    sec.className = "cluster new-cluster-placeholder ex-folder open";
    sec.dataset.clusterIdx = "new";
    const hd = document.createElement("div");
    hd.className = "ex-folder-hd";
    hd.innerHTML = `<span class="ex-chev">▶</span><span class="ex-name">+ New cluster</span>`;
    sec.appendChild(hd);
    const body = document.createElement("div");
    body.className = "ex-folder-body";
    sec.appendChild(body);
    return sec;
  }

  function render() {
    const root = document.getElementById("explorer");
    root.innerHTML = "";
    clusters.forEach((c, ci) => root.appendChild(buildExplorerFolder(c, ci)));
    if (ungrouped.length) root.appendChild(buildExplorerUngrouped());
    root.appendChild(buildExplorerNewSlot());
    initSortable();
    window.__clusterState = { clusters, ungrouped, threshold };
  }

  function getOverlap(a, b) {
    if (a === b) return 1;
    return (jaccard[a]?.[b]) ?? (jaccard[b]?.[a]) ?? 0;
  }

  function canDropInto(kw, targetSection) {
    if (!targetSection) return false;
    const idx = targetSection.dataset.clusterIdx;
    if (idx === "ungrouped" || idx === "new") return true;
    const cluster = clusters[parseInt(idx, 10)];
    if (!cluster) return false;
    if (cluster.members.includes(kw)) return false;
    if ((volumes[kw] || 0) > (volumes[cluster.primary] || 0)) return false;
    if (getOverlap(kw, cluster.primary) < threshold) return false;
    return true;
  }

  function highlightValidTargets(kw) {
    document.querySelectorAll("section.cluster").forEach(sec => {
      sec.classList.remove("drop-ok", "drop-block");
      if (sec.contains(document.querySelector(`.kw-row[data-kw="${CSS.escape(kw)}"]`))) return;
      sec.classList.add(canDropInto(kw, sec) ? "drop-ok" : "drop-block");
    });
  }

  function clearHighlights() {
    document.querySelectorAll("section.cluster").forEach(sec => sec.classList.remove("drop-ok", "drop-block"));
  }

  function makeSortable(sec) {
    const target = sec.querySelector(".ex-folder-body") || sec;
    Sortable.create(target, {
      group: "clusters",
      draggable: ".kw-row",
      animation: 160,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      dragClass: "sortable-drag",
      onStart: evt => {
        isDragging = true;
        if (hoveredKw) { hoveredKw = null; applyHoverState(null); }
        const kw = evt.item?.dataset?.kw;
        if (kw) highlightValidTargets(kw);
        document.querySelectorAll(".ex-folder:not(.open)").forEach(f => {
          f.dataset.dragExpanded = "1";
          f.classList.add("open");
        });
      },
      onMove: evt => {
        const kw = evt.dragged?.dataset?.kw;
        const targetSection = evt.to.closest("section.cluster") || evt.to;
        return canDropInto(kw, targetSection);
      },
      onEnd: () => {
        document.querySelectorAll(".ex-folder[data-drag-expanded]").forEach(f => {
          f.classList.remove("open");
          delete f.dataset.dragExpanded;
        });
        clearHighlights();
        syncFromDOM();
        isDragging = false;
        if (window.ClusterGraph) window.ClusterGraph.refresh(clusters, ungrouped, threshold);
      },
    });
  }

  function initSortable() {
    document.querySelectorAll("section.cluster").forEach(sec => makeSortable(sec));
  }

  function rebuildRows(sec, kws, primary) {
    const body = sec.querySelector(".ex-folder-body") || sec;
    body.querySelectorAll(".kw-row").forEach(r => r.remove());
    kws.forEach(kw => {
      const row = makeKwRow(kw, primary);
      if (kw === selectedKw) row.classList.add("selected");
      body.appendChild(row);
    });
  }

  function syncFromDOM() {
    clusters  = [];
    ungrouped = [];
    const sections = Array.from(document.querySelectorAll("section.cluster"));
    const toRemove = [];
    let placeholderUpgraded = false;

    sections.forEach(sec => {
      const idx     = sec.dataset.clusterIdx;
      const members = Array.from(sec.querySelectorAll(".kw-row")).map(r => r.dataset.kw);

      if (idx === "ungrouped") {
        ungrouped = members;
        const badge = sec.querySelector(".ex-badge");
        if (badge) badge.textContent = members.length + " kw";
        if (!members.length) toRemove.push(sec);
        else rebuildRows(sec, members, null);
        return;
      }

      if (idx === "new") {
        if (!members.length) return;
        sec.dataset.clusterIdx = "";
        sec.classList.remove("new-cluster-placeholder");
        const hd = sec.querySelector(".ex-folder-hd");
        if (hd) {
          hd.innerHTML = `
            <span class="ex-chev">▶</span>
            <span class="ex-number">--</span>
            <span class="ex-name"></span>
            <span class="ex-badge"></span>
            <span class="ex-vol"></span>`;
          hd.addEventListener("click", () => sec.classList.toggle("open"));
        }
        placeholderUpgraded = true;
      }

      if (!members.length) { toRemove.push(sec); return; }

      const primary = members.reduce((a, b) => (volumes[a]||0) >= (volumes[b]||0) ? a : b);
      const volume  = members.reduce((s, k) => s + (volumes[k]||0), 0);
      clusters.push({ primary, members, volume });

      const nameEl  = sec.querySelector(".ex-name");
      if (nameEl) { nameEl.textContent = primary; nameEl.title = primary; }
      const badgeEl = sec.querySelector(".ex-badge");
      if (badgeEl) badgeEl.textContent = members.length + " kw";
      const volEl   = sec.querySelector(".ex-vol");
      if (volEl) volEl.textContent = fmtInt(volume);

      rebuildRows(sec, members, primary);
    });

    toRemove.forEach(sec => sec.remove());

    // Renumber
    let ci = 0;
    document.querySelectorAll("section.cluster").forEach(sec => {
      const idx = sec.dataset.clusterIdx;
      if (idx === "ungrouped" || idx === "new") return;
      sec.dataset.clusterIdx = String(ci);
      // ★ reassign color after renumber
      sec.style.setProperty("--folder-color", CLUSTER_COLORS[ci % CLUSTER_COLORS.length]);
      const numEl = sec.querySelector(".ex-number");
      if (numEl) numEl.textContent = pad2(ci + 1);
      ci++;
    });

    if (placeholderUpgraded) {
      const root  = document.getElementById("explorer");
      const fresh = buildExplorerNewSlot();
      root.appendChild(fresh);
      makeSortable(fresh);
    }

    window.__clusterState = { clusters, ungrouped, threshold };
  }

  // ----- threshold slider -----
  document.getElementById("threshold").addEventListener("input", e => {
    threshold = parseFloat(e.target.value);
    document.getElementById("threshold-value").textContent = threshold.toFixed(2);
    updateSliderFill();
    recomputeClusters();
    render();
    if (window.ClusterGraph) window.ClusterGraph.refresh(clusters, ungrouped, threshold);
  });

  function recomputeClusters() {
    const sorted   = [...keywords].sort((a, b) => (volumes[b]||0) - (volumes[a]||0));
    const assigned = new Set();
    const next     = [];
    for (const primary of sorted) {
      if (assigned.has(primary)) continue;
      const c = { primary, members: [primary], volume: volumes[primary] || 0 };
      assigned.add(primary);
      const primaryVol = volumes[primary] || 0;
      for (const kw of sorted) {
        if (assigned.has(kw)) continue;
        const sim = (jaccard[primary]?.[kw]) ?? (jaccard[kw]?.[primary]) ?? 0;
        if (sim < threshold) continue;
        if ((volumes[kw]||0) > primaryVol) continue;
        c.members.push(kw);
        c.volume += volumes[kw] || 0;
        assigned.add(kw);
      }
      next.push(c);
    }
    clusters  = next;
    ungrouped = keywords.filter(k => !assigned.has(k));
  }

  // ----- save & close -----
  document.getElementById("save").addEventListener("click", save);

  function save() {
    syncFromDOM();
    fetch("/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clusters, ungrouped, threshold }),
    })
      .then(r => r.text())
      .then(() => showSavedPage())
      .catch(err => {
        // TypeError = network error = no server running (demo / preview mode).
        // Don't show saved page; just log. In production the server is always up.
        if (err instanceof TypeError) {
          console.log('[demo] No server — skipping showSavedPage.');
          return;
        }
        showSavedPage();
      });
  }

  function showSavedPage() {
    const totalKw  = clusters.reduce((s, c) => s + c.members.length, 0) + ungrouped.length;
    const brand    = payload.brand || "AGENT-SEO-TOOLBOX";
    const statePath = payload.state_path || "";
    document.body.innerHTML = `
      <div class="saved-page">
        <div class="eyebrow">
          <span class="brand">${escapeHtml(brand)}</span>
          <span class="dot">·</span><span>SAVED</span>
        </div>
        <h1 class="display"><em>Done.</em></h1>
        <div class="hairline"></div>
        <p class="lede">${clusters.length} cluster${clusters.length===1?"":"s"}, ${totalKw} keyword${totalKw===1?"":"s"}, threshold ${threshold.toFixed(2)}.</p>
        <p>State written to:</p>
        <pre class="path">${escapeHtml(statePath)}</pre>
        <p>Return to your terminal — Claude can read the state file now.</p>
      </div>`;
  }

  // ----- countdown -----
  let secondsLeft = payload.session_seconds;
  const cd = document.getElementById("countdown");
  const tl = document.getElementById("time-left");

  function tick() {
    if (secondsLeft <= 0) { save(); return; }
    const m = pad2(Math.floor(secondsLeft / 60));
    const s = pad2(secondsLeft % 60);
    tl.textContent = `${m}:${s}`;
    cd.classList.remove("warn", "danger");
    if (secondsLeft <= 60)        cd.classList.add("danger");
    else if (secondsLeft <= 300)  cd.classList.add("warn");
    secondsLeft--;
  }
  tick();
  setInterval(tick, 1000);

  // ----- init -----
  render();
  // Wait for cluster-graph-polished.js to define window.ClusterGraph,
  // then trigger the first render (gives graph-pane real clientWidth/Height).
  (function waitForGraph() {
    if (window.ClusterGraph) {
      window.ClusterGraph.refresh(clusters, ungrouped, threshold);
    } else {
      setTimeout(waitForGraph, 20);
    }
  }());
}());

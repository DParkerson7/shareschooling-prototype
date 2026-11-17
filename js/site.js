/*
  ShareSchooling site script. Every page is plain HTML built by
  tools/build_site.py; this adds the interactive parts:
  menu, ZIP/city search, filters, distance sorting, the county map
  (cluster, zoom, pan, preview) and the (not yet connected) forms.
*/
(() => {
  const root = document.body.dataset.root || "";
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const params = new URLSearchParams(location.search);

  /* ---------- Menu ---------- */
  const navToggle = $(".nav-toggle");
  if (navToggle) {
    navToggle.addEventListener("click", () => {
      const open = $("#site-nav").classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  $$("[data-jump]").forEach((select) =>
    select.addEventListener("change", () => { if (select.value) location.href = select.value; }));

  /* ---------- Zip lookup ---------- */
  let zipData;
  function loadZips() {
    if (!zipData) {
      zipData = Promise.all([
        fetch(root + "data/zips.json").then((r) => r.json()),
        fetch(root + "data/county-routes.json").then((r) => r.json()),
      ]).then(([z, routes]) => ({ zips: z.zips, routes }));
    }
    return zipData;
  }

  function zipStatusFor(form) {
    const scope = form.closest("[data-filterbar]") || form.parentElement;
    return $("[data-zip-status]", scope);
  }

  function showMessage(el, parts) {
    el.replaceChildren(...parts.map((p) => (typeof p === "string" ? document.createTextNode(p) : p)));
  }

  function link(href, text) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    return a;
  }

  function outsideCoverage(query) {
    return [
      `We don't have local listings for ${query} yet. The pilot covers West Tennessee and DeSoto County, MS. Meanwhile, see `,
      link(root + "online.html", "online options"), ".",
    ];
  }

  let placeData;
  function loadPlaces() {
    if (!placeData) placeData = fetch(root + "data/places.json").then((r) => r.json());
    return placeData;
  }

  function normPlace(text) {
    return String(text).toLowerCase().replace(/\./g, " ").replace(/\bcounty\b/g, " ").replace(/[^a-z0-9]+/g, " ").trim();
  }

  function onThisCounty(url) {
    const path = location.pathname.replace(/\/index\.html$/, "");
    const target = "/" + String(url).replace(/\/index\.html$/, "").replace(/\/$/, "");
    return path.endsWith(target) || path.includes(target + "/");
  }

  const preset = params.get("city") || params.get("zip") || "";
  $$("[data-zip-form], [data-place-form]").forEach((form) => {
    const input = $("input", form);
    if (preset && !input.value) input.value = preset;
    input.addEventListener("input", () => {
      $$("[data-zip-form] input, [data-place-form] input").forEach((other) => {
        if (other !== input) other.value = input.value;
      });
    });
    form.addEventListener("submit", (e) => { e.preventDefault(); runPlaceSearch(form); });
  });

  async function runPlaceSearch(form) {
    const status = form.dataset.status
      ? document.getElementById(form.dataset.status)
      : zipStatusFor(form);
    const raw = $("input", form).value.trim();
    if (!raw) {
      showMessage(status, ["Enter a ZIP code or a city name."]);
      return;
    }
    if (/^\d{5}$/.test(raw)) {
      try {
        const { zips, routes } = await loadZips();
        const hit = zips[raw];
        if (!hit || !routes[hit[0]]) {
          showMessage(status, outsideCoverage(raw));
          return;
        }
        const url = routes[hit[0]][0];
        if ($("[data-map]") && onThisCounty(url)) {
          const q = new URLSearchParams(location.search);
          q.set("zip", raw);
          q.delete("city");
          history.replaceState(null, "", location.pathname + "?" + q.toString().replace(/%2C/g, ","));
          showMessage(status, []);
          document.dispatchEvent(new CustomEvent("ss:center-zip", { detail: { zip: raw, lat: hit[1], lon: hit[2] } }));
          if (bar) sortByDistance(raw, bar);
          return;
        }
        location.href = root + url + "?zip=" + raw;
      } catch (err) {
        showMessage(status, ["Search couldn't load. Please try again."]);
      }
      return;
    }
    try {
      const places = await loadPlaces();
      const parsed = stripState(raw, places.states || {});
      const key = normPlace(parsed.q);
      if (!key) {
        showMessage(status, outsideCoverage(raw));
        return;
      }
      const wantCounty = /\bcounty\b/i.test(raw);
      let hits = (wantCounty ? places.counties[key] : places.cities[key]) || [];
      if (!hits.length) hits = (wantCounty ? places.cities[key] : places.counties[key]) || [];
      if (parsed.state) hits = hits.filter((h) => h.state === parsed.state);
      if (!hits.length) {
        showMessage(status, outsideCoverage(raw));
        return;
      }
      const chosen = choosePlace(hits);
      if (!chosen) {
        const parts = ["More than one place matches. "];
        hits.forEach((hit, i) => {
          if (i) parts.push(" · ");
          const dest = (hit.countyUrl || hit.url) + (hit.county ? "?city=" + encodeURIComponent(hit.name) : "");
          parts.push(link(root + dest, hit.name + ", " + hit.state));
        });
        parts.push(".");
        showMessage(status, parts);
        return;
      }
      const countyUrl = chosen.countyUrl || chosen.url;
      const cityName = chosen.county ? chosen.name : "";
      if ($("[data-map]") && onThisCounty(countyUrl) && (!cityName || mapHasCity(cityName, chosen.state))) {
        const q = new URLSearchParams(location.search);
        if (cityName) { q.set("city", cityName); q.delete("zip"); }
        history.replaceState(null, "", location.pathname + "?" + q.toString().replace(/%2C/g, ","));
        showMessage(status, []);
        document.dispatchEvent(new CustomEvent("ss:center-city", { detail: { city: cityName, state: chosen.state, lat: chosen.lat, lon: chosen.lon } }));
        return;
      }
      location.href = root + countyUrl + (cityName ? "?city=" + encodeURIComponent(cityName) : "");
    } catch (err) {
      showMessage(status, ["Search couldn't load. Please try again."]);
    }
  }

  function stripState(raw, states) {
    const names = Object.entries(states).sort((a, b) => b[1].length - a[1].length);
    const lower = raw.toLowerCase();
    for (const [code, name] of names) {
      const n = name.toLowerCase();
      if (lower === n) return { q: "", state: code };
      if (lower.endsWith(", " + n) || lower.endsWith(" " + n)) {
        return { q: raw.slice(0, raw.length - name.length).replace(/[,\s]+$/, ""), state: code };
      }
    }
    const code = raw.match(/^(.*?)[,\s]+([A-Za-z]{2})$/);
    if (code && states[code[2].toUpperCase()]) return { q: code[1], state: code[2].toUpperCase() };
    return { q: raw, state: null };
  }

  function choosePlace(hits) {
    const state = document.body.dataset.state || "";
    const county = (document.body.dataset.county || "").toLowerCase();
    return hits.find((h) => h.state === state && (h.county || "").toLowerCase() === county)
      || hits.find((h) => h.state === state)
      || (hits.length === 1 ? hits[0] : null);
  }

  function mapHasCity(city, state) {
    const node = $("[data-map-pins]");
    if (!node) return false;
    try {
      const pins = JSON.parse(node.textContent);
      return pins.some((p) => (p.city || "").toLowerCase() === city.toLowerCase() && p.state === state);
    } catch (err) {
      return false;
    }
  }

  /* ---------- Filters ---------- */
  const bar = $("[data-filterbar]");
  if (bar) initFilters(bar);

  function initFilters(bar) {
    const panel = $("#filter-panel");
    const toggle = $("[data-filters-toggle]", bar);
    const chips = $$("[data-chip]", bar);
    const reach = $('[data-filter="reach"]', bar);
    const delivery = $('[data-filter="delivery"]', bar);
    const faithInputs = $$('input[name="faith"]', bar);
    const cards = $$("main [data-listing]");

    // Read filters from the address (e.g. ?cat=co-ops,tutors&faith=secular).
    const cats = new Set((params.get("cat") || "").split(",").filter(Boolean));
    chips.forEach((c) => c.setAttribute("aria-pressed", String(cats.has(c.dataset.chip) && !c.disabled)));
    reach.value = params.get("reach") || "";
    delivery.value = params.get("delivery") || "";
    const faith = params.get("faith") || "";
    faithInputs.forEach((i) => { i.checked = i.value === faith; });

    toggle.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      toggle.setAttribute("aria-expanded", String(!panel.hidden));
    });
    chips.forEach((c) => c.addEventListener("click", () => {
      c.setAttribute("aria-pressed", String(c.getAttribute("aria-pressed") !== "true"));
      apply();
    }));
    [reach, delivery, ...faithInputs].forEach((el) => el.addEventListener("change", apply));
    $("[data-clear-filters]", bar).addEventListener("click", () => {
      chips.forEach((c) => c.setAttribute("aria-pressed", "false"));
      reach.value = delivery.value = "";
      faithInputs.forEach((i) => { i.checked = i.value === ""; });
      apply();
    });

    function current() {
      return {
        cats: chips.filter((c) => c.getAttribute("aria-pressed") === "true").map((c) => c.dataset.chip),
        reach: reach.value,
        delivery: delivery.value,
        faith: (faithInputs.find((i) => i.checked) || {}).value || "",
      };
    }

    function matches(card, f) {
      const d = card.dataset;
      if (f.cats.length && !f.cats.includes(d.cat)) return false;
      if (f.reach && d.reach !== f.reach) return false;
      // "In person" and "Online" also include programs offered both ways.
      if (f.delivery && d.delivery !== f.delivery && !(f.delivery !== "Both" && d.delivery === "Both")) return false;
      // Listings with unknown faith appear only under All.
      if (f.faith && d.faith !== f.faith) return false;
      return true;
    }

    function apply() {
      const f = current();
      const shown = new Set();
      cards.forEach((card) => {
        const ok = matches(card, f);
        card.hidden = !ok;
        if (ok) shown.add(card.dataset.id);
      });
      $$("[data-result]").forEach((row) => { row.hidden = !shown.has(row.dataset.id); });
      const railEmpty = $("[data-rail-empty]");
      if (railEmpty) railEmpty.hidden = !!$("[data-result]:not([hidden])");
      $$("main [data-list]").forEach((list) => {
        const empty = list.nextElementSibling;
        if (empty && empty.hasAttribute("data-empty")) empty.hidden = !!$("[data-listing]:not([hidden])", list);
      });
      $$("main [data-section]").forEach((s) => { s.hidden = !$("[data-listing]:not([hidden])", s); });
      $$("main [data-all-empty]").forEach((el) => {
        el.hidden = !!$("[data-section]:not([hidden])", el.parentElement);
      });

      // The count covers the main list; the "Also available" column is extra.
      const mainCards = cards.filter((c) => !c.closest(".also-col"));
      const mainShown = new Set(mainCards.filter((c) => !c.hidden).map((c) => c.dataset.id)).size;
      const total = new Set(mainCards.map((c) => c.dataset.id)).size;
      $("[data-results-count]", bar).textContent = `Showing ${mainShown} of ${total} listings`;
      const active = f.cats.length + !!f.reach + !!f.delivery + !!f.faith;
      const badge = $("[data-filter-count]", bar);
      badge.hidden = !active;
      badge.textContent = active;
      const listCount = $("[data-list-count]");
      if (listCount) listCount.textContent = String(mainShown);
      const unpinned = mainCards.filter((c) => !c.hidden && c.dataset.lat == null).length;
      const note = unpinned
        ? `${unpinned} ${unpinned === 1 ? "listing has" : "listings have"} no fixed spot on the map. ${unpinned === 1 ? "It stays" : "They stay"} in the list.`
        : "";
      $$("[data-unpinned-note]").forEach((el) => { el.textContent = note; el.hidden = !note; });
      document.dispatchEvent(new CustomEvent("ss:filtered"));

      const q = new URLSearchParams(location.search);
      const set = (k, v) => (v ? q.set(k, v) : q.delete(k));
      set("cat", f.cats.join(","));
      set("reach", f.reach);
      set("delivery", f.delivery);
      set("faith", f.faith);
      const qs = q.toString().replace(/%2C/g, ",");
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }

    apply();
    if (current().cats.length || reach.value || delivery.value || current().faith) {
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    }
    if (params.get("zip")) sortByDistance(params.get("zip"), bar);
  }

  /* ---------- Distance from a zip code ---------- */
  function miles(lat1, lon1, lat2, lon2) {
    const rad = Math.PI / 180;
    const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(a));
  }

  async function sortByDistance(zip, bar) {
    const status = $("[data-zip-status]", bar);
    try {
      const { zips } = await loadZips();
      const hit = zips[zip];
      if (!hit) return;
      const [, zlat, zlon] = hit;
      $$("main [data-listing]").forEach((card) => {
        const { lat, lon } = card.dataset;
        card.dataset.dist = lat ? miles(zlat, zlon, +lat, +lon) : "";
        const label = $("[data-distance]", card);
        if (label) label.textContent = lat ? `About ${Math.round(card.dataset.dist)} mi from ${zip}` : "";
      });
      $$("main [data-list]").forEach((list) => {
        const items = $$(":scope > [data-listing]", list);
        const key = (c) => [
          c.dataset.featured === "1" ? 0 : 1,
          +c.dataset.confirm,
          c.dataset.dist === "" ? Infinity : +c.dataset.dist,
        ];
        items.sort((a, b) => {
          const ka = key(a), kb = key(b);
          for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
          return a.dataset.name.localeCompare(b.dataset.name);
        });
        list.append(...items);
      });
      const rail = $("[data-results-rail] ul");
      if (rail) {
        const items = $$(":scope > [data-result]", rail);
        const distOf = (row) => {
          const card = $(`[data-listing][data-id="${CSS.escape(row.dataset.id)}"]`);
          return card && card.dataset.dist !== "" && card.dataset.dist != null ? +card.dataset.dist : Infinity;
        };
        items.sort((a, b) => distOf(a) - distOf(b) || a.dataset.name.localeCompare(b.dataset.name));
        rail.append(...items);
      }
      showMessage(status, [`Sorted by distance from ${zip}. Listings without a map location are listed last.`]);
    } catch (err) {
      /* Sorting is a nice-to-have; the list still works without it. */
    }
  }

  /* ---------- Map or list (phones) ---------- */
  function setBrowseMode(mode) {
    const explorer = $("[data-explorer]");
    if (!explorer) return;
    explorer.classList.toggle("view-map", mode === "map");
    explorer.classList.toggle("view-list", mode === "list");
    $$("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === mode)));
    if (mode === "map") document.dispatchEvent(new CustomEvent("ss:map-shown"));
  }
  $$("[data-view]").forEach((b) => b.addEventListener("click", () => setBrowseMode(b.dataset.view)));

  /* ---------- Interactive map ---------- */
  $$("[data-map]").forEach(initMap);

  function initMap(stage) {
    const svg = $("svg.map-svg", stage);
    const layer = $("[data-marker-layer]", svg);
    const dataNode = $("[data-map-pins]", stage);
    if (!svg || !layer || !dataNode) return;
    const pins = JSON.parse(dataNode.textContent);
    const byId = new Map(pins.map((p) => [p.id, p]));
    const homeBox = parseBox(svg.dataset.home || svg.getAttribute("viewBox"));
    const allowPreview = stage.dataset.allowPreview !== "0";
    const preview = $("[data-preview]", stage);
    let view = { ...homeBox };
    let spider = null;
    let selectedId = null;
    let hoveredId = null;
    let previewGroup = [];
    let previewIndex = 0;
    let previewOpen = false;
    let returnFocus = null;
    let suppressClick = false;
    let minW = 1;
    let maxW = 100;
    let limits = homeBox;
    const phone = () => window.matchMedia("(max-width: 899px)").matches;
    const sameCityPx = () => (phone() ? 280 : 320);
    const otherCityPx = () => (phone() ? 18 : 26);

    function parseBox(str) {
      const [x, y, w, h] = String(str).trim().split(/[\s,]+/).map(Number);
      return { x, y, w, h };
    }
    function metrics() {
      const rect = svg.getBoundingClientRect();
      const s = rect.width > 0 && view.w > 0 ? Math.min(rect.width / view.w, rect.height / view.h) : 1;
      const offX = (rect.width - view.w * s) / 2;
      const offY = (rect.height - view.h * s) / 2;
      return { rect, s, offX, offY };
    }
    function aspect() {
      const rect = svg.getBoundingClientRect();
      return rect.height > 0 ? rect.width / rect.height : 1.4;
    }
    function frame(box) {
      const a = aspect();
      let { x, y, w, h } = box;
      w = Math.max(w, 0.05);
      h = Math.max(h, 0.05);
      if (w / h < a) { const nw = h * a; x -= (nw - w) / 2; w = nw; }
      else { const nh = w / a; y -= (nh - h) / 2; h = nh; }
      return { x, y, w, h };
    }
    function bboxOf(list) {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      list.forEach((p) => { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y); });
      if (!list.length || !isFinite(x0)) return null;
      return { x: x0, y: y0, w: Math.max(x1 - x0, 0.02), h: Math.max(y1 - y0, 0.02) };
    }
    function unionBox(a, b) {
      if (!b) return { ...a };
      const x0 = Math.min(a.x, b.x), y0 = Math.min(a.y, b.y);
      const x1 = Math.max(a.x + a.w, b.x + b.w), y1 = Math.max(a.y + a.h, b.y + b.h);
      return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
    }
    function pad(box, frac) {
      const m = Math.max(box.w, box.h) * frac;
      return { x: box.x - m, y: box.y - m, w: box.w + m * 2, h: box.h + m * 2 };
    }
    function configureLimits() {
      const framed = frame(homeBox);
      const all = unionBox(homeBox, bboxOf(pins));
      limits = pad(all, 0.35);
      minW = framed.w / 16;
      maxW = Math.max(framed.w * 1.45, limits.w * 1.2);
    }
    function clampView(box) {
      const a = aspect();
      let w = Math.min(maxW, Math.max(minW, box.w));
      let h = w / a;
      let x = box.x + box.w / 2 - w / 2;
      let y = box.y + box.h / 2 - h / 2;
      const cx = Math.min(Math.max(x + w / 2, limits.x), limits.x + limits.w);
      const cy = Math.min(Math.max(y + h / 2, limits.y), limits.y + limits.h);
      return { x: cx - w / 2, y: cy - h / 2, w, h };
    }
    function applyView() {
      svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
    }
    function visiblePins() {
      const cards = $$("main [data-listing]");
      if (!cards.length) return pins.slice();
      const shown = new Set(cards.filter((c) => !c.hidden).map((c) => c.dataset.id));
      return pins.filter((p) => shown.has(p.id));
    }
    function screenOf(p, m) {
      return { sx: m.offX + (p.x - view.x) * m.s, sy: m.offY + (p.y - view.y) * m.s };
    }
    function clusterPins(list) {
      const m = metrics();
      const items = list.map((p) => ({ pin: p, ...screenOf(p, m) }));
      const parent = items.map((_, i) => i);
      const find = (i) => { while (parent[i] !== i) i = parent[i] = parent[parent[i]]; return i; };
      const unite = (a, b) => { a = find(a); b = find(b); if (a !== b) parent[b] = a; };
      const near = (a, b) => {
        const d = Math.hypot(a.sx - b.sx, a.sy - b.sy);
        const same = a.pin.city && a.pin.city === b.pin.city && a.pin.state === b.pin.state;
        return d <= (same ? sameCityPx() : otherCityPx());
      };
      for (let i = 0; i < items.length; i++) {
        for (let j = i + 1; j < items.length; j++) if (near(items[i], items[j])) unite(i, j);
      }
      const groups = new Map();
      items.forEach((item, i) => {
        const id = find(i);
        if (!groups.has(id)) groups.set(id, []);
        groups.get(id).push(item.pin);
      });
      return [...groups.values()].map((members) => {
        const sx = members.reduce((s, p) => s + screenOf(p, m).sx, 0) / members.length;
        const sy = members.reduce((s, p) => s + screenOf(p, m).sy, 0) / members.length;
        return { members, sx, sy, x: view.x + (sx - m.offX) / m.s, y: view.y + (sy - m.offY) / m.s };
      });
    }
    function mstMaxEdge(members) {
      if (members.length < 2) return 0;
      const used = [0];
      const dist = members.map((p, i) => Math.hypot(p.x - members[0].x, p.y - members[0].y));
      let maxE = 0;
      while (used.length < members.length) {
        let best = -1, bestD = Infinity;
        for (let i = 0; i < members.length; i++) {
          if (used.includes(i)) continue;
          if (dist[i] < bestD) { bestD = dist[i]; best = i; }
        }
        if (best < 0) break;
        maxE = Math.max(maxE, bestD);
        used.push(best);
        for (let i = 0; i < members.length; i++) {
          if (used.includes(i)) continue;
          dist[i] = Math.min(dist[i], Math.hypot(members[i].x - members[best].x, members[i].y - members[best].y));
        }
      }
      return maxE;
    }
    function centroid(members) {
      return {
        x: members.reduce((s, p) => s + p.x, 0) / members.length,
        y: members.reduce((s, p) => s + p.y, 0) / members.length,
      };
    }
    function svgEl(name, attrs) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
      return el;
    }
    function px(n) { return n / Math.max(metrics().s, 0.001); }
    function markerGroup(g, kind, id, label, members) {
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.setAttribute("data-marker", "");
      g.setAttribute("data-kind", kind);
      g.setAttribute("data-marker-id", id);
      if (members) g.dataset.members = members.map((p) => p.id).join("|");
      g.setAttribute("aria-label", label);
      return g;
    }
    function drawPin(g, p, x, y, selected) {
      const r = px(phone() ? 11 : 9);
      const hit = px(phone() ? 22 : 16);
      if (selected || p.id === hoveredId) g.append(svgEl("circle", { class: "select-ring", cx: x, cy: y, r: r + px(8), "stroke-width": 2 }));
      g.append(svgEl("circle", { class: "focus-ring", cx: x, cy: y, r: r + px(5), fill: "none" }));
      const mark = svgEl("circle", { class: `mark ${p.exact ? "exact" : "approx"}`, cx: x, cy: y, r, "stroke-width": p.exact ? 2.5 : 3.2 });
      g.append(mark);
      g.append(svgEl("circle", { class: "hit", cx: x, cy: y, r: hit }));
      g.classList.add("pin-" + p.token);
      if (p.dim && p.id !== selectedId) g.classList.add("is-dim");
      if (p.id === hoveredId) g.classList.add("is-hot");
      if (selected) g.classList.add("is-selected");
    }
    function drawCluster(g, group) {
      const r = px(phone() ? 22 : 20);
      const c = centroid(group.members);
      g.append(svgEl("circle", { cx: c.x, cy: c.y, r: r + px(6), fill: "#1F6F78", "fill-opacity": "0.18" }));
      g.append(svgEl("circle", { class: "focus-ring", cx: c.x, cy: c.y, r: r + px(4), fill: "none" }));
      g.append(svgEl("circle", { class: "cluster-bubble", cx: c.x, cy: c.y, r, "stroke-width": 3 }));
      const text = svgEl("text", { class: "cluster-count", x: c.x, y: c.y + px(phone() ? 6 : 5), "font-size": px(phone() ? 16 : 15) });
      text.textContent = String(group.members.length);
      g.append(text);
      g.append(svgEl("circle", { class: "hit", cx: c.x, cy: c.y, r: px(phone() ? 22 : 20) }));
      if (group.members.every((p) => p.dim)) g.classList.add("is-dim");
      if (group.members.some((p) => p.id === hoveredId)) g.classList.add("is-hot");
    }
    function sharedCity(members) {
      const city = members[0].city;
      return city && members.every((p) => p.city === city) ? city : "";
    }
    const labels = [];
    function addLabel(x, y, text, anchor) {
      const m = metrics();
      const sx = m.offX + (x - view.x) * m.s;
      const sy = m.offY + (y - view.y) * m.s;
      if (labels.some((l) => Math.hypot(l.sx - sx, l.sy - sy) < 28)) return;
      labels.push({ sx, sy });
      const node = svgEl("text", { class: "city-label", x, y, "text-anchor": anchor || "middle", "font-size": px(12), "stroke-width": px(3) });
      node.textContent = text;
      layer.append(node);
    }
    function render() {
      if (svg.getBoundingClientRect().width < 20) return;
      if (spider && spider.ready && view.w > spider.scale * 1.35) spider = null;
      const list = visiblePins();
      const spiderIds = spider ? new Set(spider.members.map((p) => p.id)) : new Set();
      const rest = list.filter((p) => !spiderIds.has(p.id));
      labels.length = 0;
      layer.replaceChildren();
      const groups = clusterPins(rest);
      if (spider) {
        const members = spider.members.filter((p) => list.some((v) => v.id === p.id));
        if (members.length < 2) spider = null;
        else {
          const c = centroid(members);
          const radius = px(Math.max(36, 16 + members.length * 4));
          members.forEach((p) => {
            const i = members.indexOf(p);
            const a = -Math.PI / 2 + (2 * Math.PI * i) / members.length;
            const x = c.x + Math.cos(a) * radius;
            const y = c.y + Math.sin(a) * radius;
            layer.append(svgEl("line", { class: "spider-line", x1: c.x, y1: c.y, x2: x, y2: y }));
            p._sx = x; p._sy = y;
          });
          const hub = markerGroup(svgEl("g", {}), "spider", "spider", `${members.length} listings. Collapse this group`, members);
          drawCluster(hub, { members });
          layer.append(hub);
          members.forEach((p) => {
            const where = p.exact ? "" : " (approximate location)";
            const g = markerGroup(svgEl("g", {}), "pin", p.id, `${p.name}, ${p.catLabel}${p.city ? ", " + p.city : ""}${where}`);
            drawPin(g, p, p._sx, p._sy, p.id === selectedId);
            layer.append(g);
          });
        }
      }
      groups.forEach((group) => {
        if (group.members.length === 1) {
          const p = group.members[0];
          const where = p.exact ? "" : " (approximate location)";
          const g = markerGroup(svgEl("g", {}), "pin", p.id, `${p.name}, ${p.catLabel}${p.city ? ", " + p.city : ""}${where}`);
          drawPin(g, p, p.x, p.y, p.id === selectedId);
          layer.append(g);
          if (p.city && list.filter((o) => o.city === p.city && o.state === p.state).length === 1) addLabel(p.x, p.y + px(22), p.city, "middle");
        } else {
          const city = sharedCity(group.members);
          const g = markerGroup(
            svgEl("g", {}), "cluster", group.members.map((p) => p.id).join("|"),
            `${group.members.length} listings${city ? " in " + city : ""}. Zoom in to choose one`,
            group.members);
          drawCluster(g, group);
          layer.append(g);
          const place = sharedCity(group.members);
          if (place) addLabel(centroid(group.members).x, centroid(group.members).y + px(phone() ? 40 : 36), place, "middle");
        }
      });
      $$("[data-legend-cat]").forEach((li) => {
        li.classList.toggle("is-off", !list.some((p) => p.cat === li.dataset.legendCat));
      });
      if (previewOpen) positionPreview();
    }
    function jump(box, done) {
      const next = clampView(frame(box));
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const from = { ...view };
      if (reduce) {
        view = next; applyView(); render(); finishSpider(); if (done) done(); return;
      }
      const t0 = performance.now();
      function step(now) {
        const t = Math.min(1, (now - t0) / 280);
        const e = 1 - (1 - t) ** 3;
        view = {
          x: from.x + (next.x - from.x) * e,
          y: from.y + (next.y - from.y) * e,
          w: from.w + (next.w - from.w) * e,
          h: from.h + (next.h - from.h) * e,
        };
        applyView();
        render();
        if (t < 1) requestAnimationFrame(step);
        else { finishSpider(); if (done) done(); }
      }
      requestAnimationFrame(step);
    }
    function finishSpider() {
      if (spider && !spider.ready) { spider.scale = view.w; spider.ready = true; }
    }
    function boxAround(members, minFrac) {
      const bb = bboxOf(members) || { x: members[0].x, y: members[0].y, w: 0.02, h: 0.02 };
      const min = frame(homeBox).w * minFrac;
      if (bb.w < min) { bb.x -= (min - bb.w) / 2; bb.w = min; }
      const minH = min / aspect();
      if (bb.h < minH) { bb.y -= (minH - bb.h) / 2; bb.h = minH; }
      return pad(bb, 0.18);
    }
    function fitTo(list, minFrac) {
      if (!list.length) { jump(homeBox); return; }
      jump(boxAround(list, minFrac == null ? (list.length === 1 ? 0.34 : 0.2) : minFrac));
    }
    function expandCluster(members, done) {
      const edge = mstMaxEdge(members);
      const width = svg.getBoundingClientRect().width || 700;
      const threshold = members.every((p) => p.city && p.city === members[0].city) ? sameCityPx() : otherCityPx();
      const splitW = edge > 0.02 ? (edge * width) / (threshold * 1.15) : 0;
      if (edge < 0.02 || splitW < minW) {
        spider = { members: members.slice(), scale: 0, ready: false };
        jump(boxAround(members, 0.28), done);
        return;
      }
      const c = centroid(members);
      const w = Math.min(view.w / 1.15, Math.max(minW, splitW));
      jump({ x: c.x - w / 2, y: c.y - w / aspect() / 2, w, h: w / aspect() }, done);
    }
    function groupFor(id) {
      const list = visiblePins();
      if (spider && spider.members.some((p) => p.id === id)) return spider.members.filter((p) => list.some((v) => v.id === p.id));
      const found = clusterPins(list).find((g) => g.members.some((p) => p.id === id));
      return found ? found.members : [byId.get(id)].filter(Boolean);
    }
    function highlight(id) {
      $$("[data-result], [data-listing]").forEach((el) => {
        const on = el.dataset.id === id;
        el.classList.toggle("is-selected", on);
        const btn = el.matches("[data-result]") ? $("button", el) : null;
        if (btn) btn.setAttribute("aria-pressed", String(on));
      });
      const row = $(`[data-result][data-id="${CSS.escape(id)}"]`);
      if (row) {
        const rail = row.closest(".results-rail");
        const list = $("ul", rail);
        if (list && list.scrollHeight > list.clientHeight + 4) {
          const listRect = list.getBoundingClientRect();
          const rowRect = row.getBoundingClientRect();
          if (rowRect.top < listRect.top) list.scrollTop -= listRect.top - rowRect.top + 8;
          else if (rowRect.bottom > listRect.bottom) list.scrollTop += rowRect.bottom - listRect.bottom + 8;
        }
      }
      const card = $(`[data-listing][data-id="${CSS.escape(id)}"]`);
      const explorer = $("[data-explorer]");
      if (card && explorer && explorer.classList.contains("view-list")) card.scrollIntoView({ block: "nearest" });
    }
    function fillPreview(id, group) {
      const pin = byId.get(id);
      if (!pin || !preview) return;
      previewGroup = group.slice().sort((a, b) => a.name.localeCompare(b.name));
      previewIndex = Math.max(0, previewGroup.findIndex((p) => p.id === id));
      const item = previewGroup[previewIndex];
      const cat = $("[data-preview-cat]", preview);
      cat.className = "pc-cat pin-" + item.token;
      cat.replaceChildren();
      const dot = document.createElement("span");
      dot.className = "mk " + (item.exact ? "solid" : "hollow") + " pin-" + item.token;
      dot.setAttribute("aria-hidden", "true");
      cat.append(dot, document.createTextNode(item.catLabel));
      $("[data-preview-name]", preview).textContent = item.name;
      const meta = [item.city && item.state ? `${item.city}, ${item.state}` : item.city || item.state, item.ages, item.faith].filter(Boolean);
      $("[data-preview-meta]", preview).textContent = meta.join(" · ");
      $("[data-preview-loc]", preview).textContent = `${item.exact ? "Exact location" : "Approximate (city only)"}${item.delivery ? " · " + item.delivery : ""}`;
      const details = $("[data-preview-link]", preview);
      details.href = root + item.url;
      const pager = $("[data-preview-pager]", preview);
      const many = previewGroup.length > 1;
      pager.hidden = !many;
      if (many) {
        const city = sharedCity(previewGroup);
        const short = phone() || !city;
        $("[data-preview-count]", preview).textContent = short
          ? `${previewIndex + 1} of ${previewGroup.length}`
          : `${previewIndex + 1} of ${previewGroup.length} in ${city}`;
      }
      selectedId = item.id;
      highlight(item.id);
    }
    function positionPreview() {
      if (!previewOpen || !preview) return;
      const item = previewGroup[previewIndex];
      if (!item) return;
      if (phone()) {
        preview.classList.add("is-sheet");
        preview.style.left = "";
        preview.style.top = "";
        return;
      }
      preview.classList.remove("is-sheet");
      const point = item._sx != null && spider && spider.members.some((p) => p.id === item.id)
        ? { x: item._sx, y: item._sy } : item;
      const m = metrics();
      const pxX = m.offX + (point.x - view.x) * m.s;
      const pxY = m.offY + (point.y - view.y) * m.s;
      const cardW = Math.min(290, stage.clientWidth - 16);
      let left = pxX + 16;
      let top = pxY - 70;
      if (left + cardW > stage.clientWidth - 8) left = pxX - cardW - 16;
      left = Math.max(8, Math.min(left, stage.clientWidth - cardW - 8));
      const cardH = preview.offsetHeight || 180;
      top = Math.max(8, Math.min(top, stage.clientHeight - cardH - 8));
      preview.style.left = left + "px";
      preview.style.top = top + "px";
    }
    function openPreview(id, group) {
      if (!allowPreview || !preview) { highlight(id); selectedId = id; render(); return; }
      returnFocus = document.activeElement;
      fillPreview(id, group && group.length ? group : [byId.get(id)]);
      preview.hidden = false;
      previewOpen = true;
      render();
      positionPreview();
      preview.focus({ preventScroll: true });
      if (phone()) requestAnimationFrame(() => preview.scrollIntoView({ block: "nearest", inline: "nearest" }));
    }
    function closePreview() {
      if (!previewOpen) return;
      previewOpen = false;
      selectedId = null;
      if (preview) preview.hidden = true;
      $$("[data-result], [data-listing]").forEach((el) => el.classList.remove("is-selected"));
      render();
      if (returnFocus && returnFocus.focus) returnFocus.focus({ preventScroll: true });
    }
    function stepPreview(delta) {
      if (previewGroup.length < 2) return;
      previewIndex = (previewIndex + delta + previewGroup.length) % previewGroup.length;
      const item = previewGroup[previewIndex];
      fillPreview(item.id, previewGroup);
      render();
      positionPreview();
    }
    function select(id) {
      const pin = byId.get(id);
      if (!pin || !visiblePins().some((p) => p.id === id)) return;
      const group = groupFor(id);
      const show = () => openPreview(id, groupFor(id));
      if (group.length > 1 && !(spider && spider.members.some((p) => p.id === id))) {
        const edge = mstMaxEdge(group);
        const span = bboxOf(group);
        const wide = span && Math.hypot(span.w, span.h) > 1.35 && edge > 0.08;
        if (!wide) {
          spider = { members: group.slice(), scale: 0, ready: false };
          jump(boxAround(group, 0.28), show);
        } else expandCluster(group, show);
        return;
      }
      show();
    }
    function clientToView(cx, cy) {
      const m = metrics();
      return { x: view.x + (cx - m.rect.left - m.offX) / m.s, y: view.y + (cy - m.rect.top - m.offY) / m.s };
    }
    function zoomAt(vx, vy, factor) {
      const origin = view;
      const w = Math.min(maxW, Math.max(minW, origin.w / factor));
      const applied = origin.w / w;
      view = clampView({
        x: vx - (vx - origin.x) / applied,
        y: vy - (vy - origin.y) / applied,
        w,
        h: w / aspect(),
      });
      applyView();
      render();
    }
    function zoomCenter(factor) {
      zoomAt(view.x + view.w / 2, view.y + view.h / 2, factor);
    }

    configureLimits();
    view = clampView(frame(homeBox));
    applyView();

    svg.addEventListener("click", (e) => {
      if (suppressClick) { suppressClick = false; return; }
      const marker = e.target.closest("[data-marker]");
      if (!marker) { closePreview(); return; }
      if (marker.dataset.kind === "cluster" || marker.dataset.kind === "spider") {
        if (marker.dataset.kind === "spider") { spider = null; render(); return; }
        expandCluster(marker.dataset.members.split("|").map((id) => byId.get(id)).filter(Boolean));
        return;
      }
      if (marker.dataset.kind === "pin") {
        selectedId = marker.dataset.markerId;
        openPreview(marker.dataset.markerId, groupFor(marker.dataset.markerId));
      }
    });
    layer.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const marker = e.target.closest("[data-marker]");
      if (!marker) return;
      e.preventDefault();
      marker.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    stage.addEventListener("keydown", (e) => {
      if (e.target.closest("[data-marker], input, textarea, button, a, select")) return;
      const step = view.w * 0.18;
      if (e.key === "+" || e.key === "=") { e.preventDefault(); zoomCenter(1.35); }
      else if (e.key === "-" || e.key === "_") { e.preventDefault(); zoomCenter(1 / 1.35); }
      else if (e.key === "0") { e.preventDefault(); fitTo(visiblePins()); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); view.x -= step; view = clampView(view); applyView(); render(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); view.x += step; view = clampView(view); applyView(); render(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); view.y -= step; view = clampView(view); applyView(); render(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); view.y += step; view = clampView(view); applyView(); render(); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && previewOpen && stage.contains(preview)) { e.preventDefault(); closePreview(); }
    });

    const pointers = new Map();
    let gesture = null;
    svg.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size >= 2) {
        const pts = [...pointers.values()];
        gesture = {
          type: "pinch",
          dist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1,
          cx: (pts[0].x + pts[1].x) / 2, cy: (pts[0].y + pts[1].y) / 2,
          view: { ...view },
        };
      } else {
        gesture = { type: "pending", id: e.pointerId, x: e.clientX, y: e.clientY, view: { ...view }, moved: false };
      }
    });
    svg.addEventListener("pointermove", (e) => {
      if (!pointers.has(e.pointerId) || !gesture) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (gesture.type === "pending" && e.pointerId === gesture.id) {
        const dx = e.clientX - gesture.x, dy = e.clientY - gesture.y;
        if (Math.hypot(dx, dy) < 6) return;
        if (e.pointerType === "touch" && Math.abs(dy) > Math.abs(dx) * 1.15) { gesture = null; return; }
        gesture.type = "pan";
        gesture.moved = true;
        svg.setPointerCapture(e.pointerId);
      }
      if (gesture.type === "pan" && e.pointerId === gesture.id) {
        const m = metrics();
        const scale = m.rect.width / gesture.view.w;
        view = clampView({ ...gesture.view, x: gesture.view.x - (e.clientX - gesture.x) / scale, y: gesture.view.y - (e.clientY - gesture.y) / scale, w: gesture.view.w, h: gesture.view.h });
        applyView();
        render();
      }
      if (gesture.type === "pinch" && pointers.size >= 2) {
        e.preventDefault();
        const pts = [...pointers.values()];
        const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
        const cx = (pts[0].x + pts[1].x) / 2, cy = (pts[0].y + pts[1].y) / 2;
        const factor = dist / gesture.dist;
        const m0 = svg.getBoundingClientRect();
        const s0 = m0.width / gesture.view.w;
        const offX = (m0.width - gesture.view.w * s0) / 2;
        const offY = (m0.height - gesture.view.h * s0) / 2;
        const vx = gesture.view.x + (gesture.cx - m0.left - offX) / s0;
        const vy = gesture.view.y + (gesture.cy - m0.top - offY) / s0;
        const w = Math.min(maxW, Math.max(minW, gesture.view.w / factor));
        const s1 = m0.width / w;
        const offX1 = (m0.width - w * s1) / 2;
        const offY1 = (m0.height - (w / aspect()) * s1) / 2;
        view = clampView({
          w, h: w / aspect(),
          x: vx - (cx - m0.left - offX1) / s1,
          y: vy - (cy - m0.top - offY1) / s1,
        });
        applyView();
        render();
      }
    });
    svg.addEventListener("pointerup", (e) => {
      if (gesture && gesture.moved) suppressClick = true;
      pointers.delete(e.pointerId);
      if (pointers.size < 2 && gesture && gesture.type === "pinch") gesture = null;
      if (pointers.size === 0) gesture = null;
    });
    svg.addEventListener("pointercancel", (e) => { pointers.delete(e.pointerId); gesture = null; });
    svg.addEventListener("wheel", (e) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      const p = clientToView(e.clientX, e.clientY);
      zoomAt(p.x, p.y, e.deltaY < 0 ? 1.18 : 1 / 1.18);
    }, { passive: false });

    $("[data-zoom-in]", stage).addEventListener("click", () => zoomCenter(1.4));
    $("[data-zoom-out]", stage).addEventListener("click", () => zoomCenter(1 / 1.4));
    $("[data-fit]", stage).addEventListener("click", () => fitTo(visiblePins()));
    const keyBtn = $("[data-key]", stage);
    if (keyBtn) keyBtn.addEventListener("click", () => {
      const key = document.getElementById("map-key");
      if (key) key.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    if (preview) {
      $("[data-preview-close]", preview).addEventListener("click", closePreview);
      $("[data-preview-prev]", preview).addEventListener("click", () => stepPreview(-1));
      $("[data-preview-next]", preview).addEventListener("click", () => stepPreview(1));
      preview.addEventListener("click", (e) => e.stopPropagation());
    }

    $$("[data-result] button").forEach((btn) => {
      const id = btn.closest("[data-result]").dataset.id;
      if (!byId.has(id)) return;
      btn.addEventListener("click", () => {
        if (phone()) setBrowseMode("map");
        requestAnimationFrame(() => select(id));
      });
      btn.addEventListener("mouseenter", () => { hoveredId = id; render(); });
      btn.addEventListener("mouseleave", () => { if (hoveredId === id) { hoveredId = null; render(); } });
    });
    $$("[data-listing]").forEach((card) => {
      if (!byId.has(card.dataset.id)) return;
      card.addEventListener("mouseenter", () => { hoveredId = card.dataset.id; render(); });
      card.addEventListener("mouseleave", () => { if (hoveredId === card.dataset.id) { hoveredId = null; render(); } });
      const link = $("a", card);
      if (!link) return;
      link.addEventListener("click", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        e.preventDefault();
        if (phone()) setBrowseMode("map");
        requestAnimationFrame(() => {
          select(card.dataset.id);
          if (stage.getBoundingClientRect().bottom < 0 || stage.getBoundingClientRect().top > window.innerHeight) {
            stage.scrollIntoView({ block: "nearest" });
          }
        });
      });
    });

    document.addEventListener("ss:filtered", () => {
      if (selectedId && !visiblePins().some((p) => p.id === selectedId)) closePreview();
      if (spider) {
        const list = visiblePins();
        spider.members = spider.members.filter((p) => list.some((v) => v.id === p.id));
        if (spider.members.length < 2) spider = null;
      }
      render();
    });
    document.addEventListener("ss:map-shown", () => requestAnimationFrame(() => { configureLimits(); applyView(); render(); positionPreview(); }));
    document.addEventListener("ss:center-zip", (e) => {
      const [x, y] = projectLonLat(e.detail.lon, e.detail.lat);
      const w = frame(homeBox).w * 0.42;
      jump({ x: x - w / 2, y: y - (w / aspect()) / 2, w, h: w / aspect() });
    });
    document.addEventListener("ss:center-city", (e) => {
      const named = visiblePins().filter((p) => (p.city || "").toLowerCase() === (e.detail.city || "").toLowerCase() && (!e.detail.state || p.state === e.detail.state));
      if (named.length) fitTo(named);
      else if (e.detail.lat != null) {
        const [x, y] = projectLonLat(e.detail.lon, e.detail.lat);
        const w = frame(homeBox).w * 0.42;
        jump({ x: x - w / 2, y: y - (w / aspect()) / 2, w, h: w / aspect() });
      }
    });
    let lastWidth = svg.getBoundingClientRect().width;
    new ResizeObserver(() => {
      const w = svg.getBoundingClientRect().width;
      if (w < 20 || Math.abs(w - lastWidth) < 1) return;
      lastWidth = w;
      const cx = view.x + view.w / 2, cy = view.y + view.h / 2;
      configureLimits();
      view = clampView({ x: cx - view.w / 2, y: cy - view.w / aspect() / 2, w: view.w, h: view.w / aspect() });
      applyView();
      render();
    }).observe(stage);

    render();
    const cityParam = params.get("city");
    if (cityParam) {
      const named = pins.filter((p) => (p.city || "").toLowerCase() === cityParam.toLowerCase());
      if (named.length) fitTo(named);
    } else if (params.get("pin") && byId.has(params.get("pin"))) select(params.get("pin"));
    else if (params.get("zip")) {
      loadZips().then(({ zips }) => {
        const hit = zips[params.get("zip")];
        if (!hit) return;
        const [x, y] = projectLonLat(hit[2], hit[1]);
        const w = frame(homeBox).w * 0.42;
        jump({ x: x - w / 2, y: y - (w / aspect()) / 2, w, h: w / aspect() });
      }).catch(() => {});
    } else if (stage.dataset.emphasize) {
      const named = pins.filter((p) => !p.dim);
      if (named.length) fitTo(named, 0.1);
    }

    stage._map = { has: (id) => byId.has(id), select };
  }

  function projectLonLat(lon, lat) {
    const rad = Math.PI / 180;
    const phi0 = 29.5 * rad, phi1 = 45.5 * rad;
    const sy0 = Math.sin(phi0);
    const n = (sy0 + Math.sin(phi1)) / 2;
    const c = 1 + sy0 * (2 * n - sy0);
    const r0 = Math.sqrt(c) / n;
    const raw = (lam, phi) => {
      const r = Math.sqrt(c - 2 * n * Math.sin(phi)) / n;
      return [r * Math.sin(lam * n), r0 - r * Math.cos(lam * n)];
    };
    const [cx, cy] = raw(-0.6 * rad, 38.7 * rad);
    const [x, y] = raw((lon + 96) * rad, lat * rad);
    return [487.5 + (x - cx) * 1300, 305 - (y - cy) * 1300];
  }

  /* ---------- Report an issue (placeholder) ---------- */
  $$("[data-report]").forEach((btn) => btn.addEventListener("click", () => {
    $("[data-report-message]").textContent = "Thanks! Reporting isn't connected yet on this test site.";
  }));

  /* ---------- Email signup ---------- */
  // TODO: connect an email provider once David picks one. Until then nothing is sent or saved.
  function subscribe(payload) {
    console.info("[ShareSchooling] signup placeholder, not sent:", payload);
    return Promise.resolve();
  }

  $$("[data-signup]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $(".form-message", form);
      const email = form.elements.email;
      if (form.elements.company.value) return; // honeypot: likely a bot
      if (!email.checkValidity() || !email.value) {
        msg.textContent = "Please enter a valid email address.";
        email.focus();
        return;
      }
      await subscribe({
        email: email.value.trim(),
        state: form.elements.state.value,
        county: form.elements.county.value.trim(),
        interests: $$('input[name="interests"]:checked', form).map((i) => i.value),
      });
      msg.textContent = "Thanks! You're signed up. (Test site: signups aren't saved yet.)";
    });
  });

  /* ---------- List your co-op or tutor ---------- */
  const listingForm = $("[data-listing-form]");
  if (listingForm) initListingForm(listingForm);

  function initListingForm(form) {
    const el = form.elements;
    const state = params.get("state");
    if (state) el.state.value = ["TN", "MS"].includes(state) ? state : "Other";
    const county = params.get("county");
    if (county) {
      const value = `${state}:${county}`;
      if ([...el.county.options].some((o) => o.value === value)) el.county.value = value;
      else { el.county.value = "other"; el.countyOther.value = county; }
    }
    const claim = params.get("claim");
    if (claim) {
      const note = $("[data-claim-note]");
      note.hidden = false;
      note.textContent = `You're claiming the listing "${claim}". [Placeholder: the claim process isn't built yet.]`;
    }

    // TODO: send submissions somewhere David approves. For now they stay in the browser.
    function submitListing(submission) {
      console.info("[ShareSchooling] listing submission placeholder, not sent:", submission);
      return Promise.resolve();
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const error = $("[data-form-error]", form);
      const message = $("[data-form-message]", form);
      error.textContent = "";
      message.replaceChildren();
      if (el.company.value) return; // honeypot: likely a bot

      const missing = [];
      if (!el.name.value.trim()) missing.push("organization name");
      if (!el.category.value) missing.push("category");
      if (!el.state.value) missing.push("state");
      if (!el.submitterEmail.value.trim() || !el.submitterEmail.checkValidity()) missing.push("your email");
      if (!el.confirm.checked) missing.push("the confirmation checkbox");
      if (missing.length) {
        error.textContent = "Please fill in: " + missing.join(", ") + ".";
        return;
      }

      const [countyState, countyName] = el.county.value.includes(":") ? el.county.value.split(":") : ["", ""];
      const submission = {
        status: "Draft",
        submittedAt: new Date().toISOString(),
        name: el.name.value.trim(),
        category: el.category.value,
        description: el.description.value.trim(),
        location: {
          state: el.state.value === "Other" ? "" : el.state.value,
          county: countyName || el.countyOther.value.trim(),
          city: el.city.value.trim(),
          zip: el.zip.value.trim(),
        },
        website: el.website.value.trim(),
        email: el.email.value.trim(),
        phone: el.phone.value.trim(),
        agesGrades: el.agesGrades.value.trim(),
        delivery: el.delivery.value,
        religiousAffiliation: el.religiousAffiliation.value || "Unknown",
        costNotes: el.costNotes.value.trim(),
        submitter: { name: el.submitterName.value.trim(), email: el.submitterEmail.value.trim() },
      };
      if (countyState && countyState !== submission.location.state) submission.location.countyState = countyState;
      await submitListing(submission);

      const blob = new Blob([JSON.stringify(submission, null, 2)], { type: "application/json" });
      const download = link(URL.createObjectURL(blob), "Download this submission (JSON)");
      download.download = "shareschooling-submission.json";
      showMessage(message, ["Thanks! This test site doesn't send submissions yet, so nothing was sent. You can keep a copy of what you entered (marked Draft): ", download]);
    });
  }
})();

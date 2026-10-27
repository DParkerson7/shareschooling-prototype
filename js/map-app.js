/*
  Homepage map and drill-down: United States › State › County › Town.
  Views are chosen from the part of the address after "#", for example
  #/state/tennessee/county/williamson/town/franklin
*/
(() => {
  const { h } = SS;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const app = document.getElementById("app");
  let data, geo;

  function svg(tag, attrs = {}, ...children) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) el.setAttribute(k, v);
    for (const c of children.flat()) if (c) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    return el;
  }

  /* ---------- Geography helpers ---------- */

  // Same math as d3.geoAlbersUsa().scale(1300).translate([487.5, 305]) for the
  // lower 48 states, which is how the map shapes in data/map.json were drawn.
  function project(lon, lat) {
    const rad = Math.PI / 180;
    const phi0 = 29.5 * rad, phi1 = 45.5 * rad;
    const sy0 = Math.sin(phi0), n = (sy0 + Math.sin(phi1)) / 2;
    const c = 1 + sy0 * (2 * n - sy0), r0 = Math.sqrt(c) / n;
    const raw = (l, p) => {
      const r = Math.sqrt(c - 2 * n * Math.sin(p)) / n;
      return [r * Math.sin(l * n), r0 - r * Math.cos(l * n)];
    };
    const k = 1300;
    const [cx, cy] = raw(-0.6 * rad, 38.7 * rad);
    const [x, y] = raw((lon + 96) * rad, lat * rad);
    return [487.5 + (x - cx) * k, 305 - (y - cy) * k];
  }

  function bbox(d) {
    const nums = d.match(/-?\d+(\.\d+)?/g).map(Number);
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < nums.length; i += 2) {
      x0 = Math.min(x0, nums[i]); x1 = Math.max(x1, nums[i]);
      y0 = Math.min(y0, nums[i + 1]); y1 = Math.max(y1, nums[i + 1]);
    }
    return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 };
  }

  function viewBoxFor(box, padRatio = 0.06) {
    const pad = Math.max(box.w, box.h) * padRatio;
    return [box.x0 - pad, box.y0 - pad, box.w + 2 * pad, box.h + 2 * pad].map((n) => n.toFixed(1)).join(" ");
  }

  const stateGeo = (state) => geo.states[state.fips];
  const countyGeo = (county) => geo.counties[county.fips];

  /* ---------- Shared view parts ---------- */

  function breadcrumbs(items) {
    return h("nav", { class: "breadcrumbs", "aria-label": "Breadcrumb" },
      h("ol", {}, items.map((item, i) => h("li", {},
        i === items.length - 1
          ? h("span", { "aria-current": "page" }, item.label)
          : h("a", { href: item.href }, item.label)))));
  }

  function backLink(href, label) {
    return h("a", { class: "back-link", href }, "← " + label);
  }

  function zipPanel() {
    const result = h("div", { class: "zip-result", "aria-live": "polite" });
    const input = h("input", { id: "zip", name: "zip", inputmode: "numeric", autocomplete: "postal-code", maxlength: "5", placeholder: "e.g. 37064" });
    const form = h("form", { class: "zip-form", role: "search" },
      h("label", { for: "zip" }, "Search by zip code"),
      h("div", { class: "row" }, input, h("button", { class: "btn", type: "submit" }, "Go")),
      h("p", { class: "hint", style: "margin:0.4rem 0 0" }, "Prototype: try 37064 (Franklin, TN) or 80903 (Colorado Springs, CO)."),
      result);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const zip = input.value.trim();
      result.className = "zip-result";
      if (!/^\d{5}$/.test(zip)) {
        result.classList.add("no-match");
        result.textContent = "Please enter a 5-digit zip code.";
        return;
      }
      const town = Object.values(data.townByKey).find((t) => t.zips.includes(zip));
      if (town) {
        location.hash = townHref(town);
        return;
      }
      result.classList.add("no-match");
      result.replaceChildren(
        "We don't have local listings for " + zip + " yet — we're growing state by state. ",
        "In the meantime, ", h("a", { href: "online.html" }, "browse Online & Nationwide resources"),
        " that are open to everyone.");
    });
    return h("section", { class: "side-panel", "aria-labelledby": "zip-heading" },
      h("h2", { id: "zip-heading" }, "Find help near you"), form);
  }

  const stateHref = (state) => "#/state/" + state.id;
  const countyHref = (county) => stateHref(county.state) + "/county/" + county.id;
  const townHref = (town) => countyHref(town.county) + "/town/" + town.id;

  function setPage(title, nodes) {
    document.title = title + " — ShareSchooling (prototype)";
    app.replaceChildren(...nodes);
    const h1 = app.querySelector("h1");
    if (h1 && !firstRender) { h1.setAttribute("tabindex", "-1"); h1.focus({ preventScroll: false }); }
    if (!firstRender) window.scrollTo(0, 0);
    firstRender = false;
  }
  let firstRender = true;

  /* ---------- Home: US map ---------- */

  function homeView() {
    const exampleFips = new Set(data.states.map((s) => s.fips));
    const states = Object.entries(geo.states).sort((a, b) => a[1].name.localeCompare(b[1].name));
    const map = svg("svg", { class: "map-svg", viewBox: geo.viewBox, role: "group", "aria-labelledby": "map-title" },
      svg("title", { id: "map-title" }, "Map of the United States. Choose a state."),
      states.map(([fips, s]) => {
        const has = exampleFips.has(fips);
        const label = s.name + (has ? " — example data available" : " — coming soon");
        return svg("a", { href: "#/state/" + SS.slugify(s.name), "aria-label": label },
          svg("path", { class: "region" + (has ? " has-data" : ""), d: s.d }, svg("title", {}, label)));
      }));

    const stateSelect = h("select", { id: "state-select" },
      h("option", { value: "" }, "Choose a state…"),
      states.map(([fips, s]) => h("option", { value: SS.slugify(s.name) }, s.name + (exampleFips.has(fips) ? " (example data)" : ""))));
    stateSelect.addEventListener("change", () => { if (stateSelect.value) location.hash = "#/state/" + stateSelect.value; });

    setPage("Find homeschool help near you", [
      h("section", { class: "hero" },
        h("h1", {}, "Join the Education Revolution!"),
        h("p", {}, "You made the right decision. You don't have to know everything or teach every subject yourself — help is closer than you think, and you can do this.")),
      h("div", { class: "map-layout" },
        h("section", { class: "map-panel", "aria-labelledby": "map-heading" },
          h("h2", { id: "map-heading" }, "Start with your state"),
          map,
          h("div", { class: "map-legend" },
            h("span", {}, h("span", { class: "swatch", style: "background:var(--color-map-active)" }), "Example data (Tennessee, Colorado)"),
            h("span", {}, h("span", { class: "swatch", style: "background:var(--color-map-state)" }), "Coming soon"))),
        h("div", {},
          zipPanel(),
          h("section", { class: "side-panel", "aria-labelledby": "pick-heading" },
            h("h2", { id: "pick-heading" }, "Or pick from a list"),
            h("label", { for: "state-select", class: "visually-hidden" }, "State"),
            stateSelect,
            h("p", { class: "hint", style: "margin:0.75rem 0 0" }, "Learning online? ",
              h("a", { href: "online.html" }, "Browse Online & Nationwide"), " — no map needed.")))),
    ]);
  }

  /* ---------- Coming soon ---------- */

  function comingSoonView(slug) {
    const match = Object.values(geo.states).find((s) => SS.slugify(s.name) === slug);
    const name = match ? match.name : "This area";
    setPage(name + " — coming soon", [
      breadcrumbs([{ label: "United States", href: "#/" }, { label: name }]),
      backLink("#/", "Back to the US map"),
      h("section", { class: "coming-soon" },
        h("div", { class: "big", "aria-hidden": "true" }, "🌱"),
        h("h1", {}, name + " is coming soon"),
        h("p", {}, "We're adding local co-ops, tutors and more state by state. Thanks for your patience — you're not alone in this!"),
        h("p", {},
          h("a", { class: "btn", href: "online.html" }, "Browse Online & Nationwide"), " ",
          h("a", { class: "btn btn-secondary", href: "list-your-resource.html" }, "List a resource in " + name))),
    ]);
  }

  /* ---------- State view ---------- */

  function stateView(state) {
    const sg = stateGeo(state);
    const counties = Object.entries(geo.counties)
      .filter(([fips]) => fips.startsWith(state.fips))
      .sort((a, b) => a[1].name.localeCompare(b[1].name));
    const exampleByFips = Object.fromEntries(state.counties.map((c) => [c.fips, c]));

    const stateBox = bbox(sg.d);
    const size = Math.max(stateBox.w, stateBox.h) / 48;
    const map = svg("svg", { class: "map-svg", viewBox: viewBoxFor(stateBox), role: "group", "aria-labelledby": "county-map-title" },
      svg("title", { id: "county-map-title" }, "Map of " + state.name + " counties. Highlighted counties have example listings."),
      counties.filter(([f]) => !exampleByFips[f]).map(([, c]) =>
        svg("path", { class: "region dim", d: c.d }, svg("title", {}, c.name + " County — coming soon"))),
      state.counties.map((county) => {
        const g = countyGeo(county);
        const b = bbox(g.d);
        // Label sits just to the right of the county so neighbouring labels don't collide.
        return svg("a", { href: countyHref(county), "aria-label": county.name },
          svg("path", { class: "region has-data", d: g.d }, svg("title", {}, county.name)),
          svg("text", { class: "town-label", x: (b.x1 + size / 3).toFixed(1), y: (b.y0 + b.h / 2 + size / 3).toFixed(1), "font-size": size.toFixed(1), "stroke-width": (size / 4).toFixed(1) }, county.name.replace(" County", "")));
      }));

    const statewide = data.listings.filter((l) => SS.isStatewideIn(l, state));
    const associations = statewide.filter((l) => l.category === "associations");
    const programs = statewide.filter((l) => l.category !== "associations");
    const countLocal = (county) => data.listings.filter((l) => SS.servesCounty(l, county)).length;

    setPage(state.name, [
      breadcrumbs([{ label: "United States", href: "#/" }, { label: state.name }]),
      backLink("#/", "Back to the US map"),
      h("h1", {}, "Homeschool help in " + state.name),
      h("section", { class: "placeholder-box section", "aria-labelledby": "law-heading" },
        h("h2", { id: "law-heading", style: "font-size:1.2rem" }, "State homeschool law basics"),
        h("p", { style: "margin:0" }, state.lawBasics)),
      h("div", { class: "map-layout section" },
        h("section", { class: "map-panel", "aria-labelledby": "counties-heading" },
          h("h2", { id: "counties-heading" }, "Choose a county"),
          map,
          h("div", { class: "map-legend" },
            h("span", {}, h("span", { class: "swatch", style: "background:var(--color-map-active)" }), "Example listings"),
            h("span", {}, h("span", { class: "swatch", style: "background:#e7ddcc" }), "Coming soon"))),
        h("section", { class: "side-panel", "aria-labelledby": "county-list-heading" },
          h("h2", { id: "county-list-heading" }, "Counties with example listings"),
          h("ul", { class: "link-list" }, state.counties.map((c) => h("li", {},
            h("a", { href: countyHref(c) }, h("span", {}, c.name), h("span", { class: "count" }, countLocal(c) + " local")))),
            h("li", {}, h("span", { class: "muted-item" }, "Other counties: coming soon"))))),
      h("section", { class: "section", "aria-labelledby": "assoc-heading" },
        h("div", { class: "section-head" }, h("h2", { id: "assoc-heading" }, "Statewide associations & legal help")),
        SS.cardList(data, associations, "No statewide associations listed yet.")),
      h("section", { class: "section", "aria-labelledby": "programs-heading" },
        h("div", { class: "section-head" }, h("h2", { id: "programs-heading" }, "Programs just for " + state.name + " families")),
        SS.cardList(data, programs, "No statewide programs listed yet.")),
    ]);
  }

  /* ---------- County view ---------- */

  function filteredSection(listings, headingId, headingText, emptyText) {
    const results = h("div", {});
    const count = h("p", { class: "results-count", "aria-live": "polite" });
    const render = (cat) => {
      const shown = cat ? listings.filter((l) => l.category === cat) : listings;
      count.textContent = "Showing " + shown.length + " of " + listings.length + " listings";
      results.replaceChildren(SS.cardList(data, shown, cat ? "No listings in this category here yet." : emptyText));
    };
    render("");
    return h("section", { class: "section", "aria-labelledby": headingId },
      h("div", { class: "section-head" }, h("h2", { id: headingId }, headingText)),
      SS.categoryFilter(data, listings, render), count, results);
  }

  function countyView(county) {
    const state = county.state;
    const g = countyGeo(county);
    const box = bbox(g.d);
    const size = Math.max(box.w, box.h) / 22;
    const map = svg("svg", { class: "map-svg", viewBox: viewBoxFor(box, 0.12), role: "group", "aria-labelledby": "town-map-title", style: "max-height:420px" },
      svg("title", { id: "town-map-title" }, "Map of " + county.name + " with its towns"),
      svg("path", { class: "region has-data", d: g.d, style: "fill:var(--color-surface-alt);stroke:var(--color-map-active);stroke-width:" + (size / 8).toFixed(2) }),
      county.towns.map((town) => {
        const [x, y] = project(town.lon, town.lat);
        return svg("a", { href: townHref(town), "aria-label": town.name },
          svg("circle", { class: "town-dot", cx: x.toFixed(2), cy: y.toFixed(2), r: (size / 1.8).toFixed(2), "stroke-width": (size / 10).toFixed(2) }),
          svg("text", { class: "town-label", x: (x + size / 1.8).toFixed(2), y: (y + size / 3).toFixed(2), "font-size": size.toFixed(2), "stroke-width": (size / 5).toFixed(2) }, town.name));
      }));

    const listings = data.listings.filter((l) => SS.servesCounty(l, county));
    const countTown = (t) => data.listings.filter((l) => SS.servesTown(l, t)).length;

    setPage(county.name + ", " + state.name, [
      breadcrumbs([{ label: "United States", href: "#/" }, { label: state.name, href: stateHref(state) }, { label: county.name }]),
      backLink(stateHref(state), "Back to " + state.name),
      h("h1", {}, county.name + ", " + state.name),
      h("div", { class: "map-layout" },
        h("section", { class: "map-panel", "aria-labelledby": "towns-map-heading" },
          h("h2", { id: "towns-map-heading" }, "Choose a town"), map),
        h("section", { class: "side-panel", "aria-labelledby": "town-list-heading" },
          h("h2", { id: "town-list-heading" }, "Towns in " + county.name),
          h("ul", { class: "link-list" }, county.towns.map((t) => h("li", {},
            h("a", { href: townHref(t) }, h("span", {}, t.name), h("span", { class: "count" }, countTown(t) + " local"))))))),
      filteredSection(listings, "county-listings-heading", "Resources serving " + county.name, "No local listings here yet."),
    ]);
  }

  /* ---------- Town view ---------- */

  function townView(town) {
    const { county, state } = town;
    const local = data.listings.filter((l) => SS.servesTown(l, town));
    const statewide = data.listings.filter((l) => SS.isStatewideIn(l, state));
    const nationwide = data.listings.filter((l) => l.reach === "Nationwide");

    const localBox = h("div", {});
    const localCount = h("p", { class: "results-count", "aria-live": "polite" });
    const alsoBox = h("div", {});
    const render = (cat) => {
      const pick = (list) => (cat ? list.filter((l) => l.category === cat) : list);
      const shown = pick(local);
      localCount.textContent = "Showing " + shown.length + " of " + local.length + " local listings";
      localBox.replaceChildren(SS.cardList(data, shown, cat ? "No local listings in this category yet — check the column on the side." : "No local listings here yet."));
      alsoBox.replaceChildren(
        h("h3", { class: "also-sub" }, "Statewide in " + state.name),
        SS.cardList(data, pick(statewide), "None in this category.", "single"),
        h("h3", { class: "also-sub" }, "Online & nationwide"),
        SS.cardList(data, SS.sortListings(pick(nationwide)).slice(0, 4), "None in this category.", "single"),
        h("p", { style: "margin-top:1rem" }, h("a", { href: "online.html" }, "See all Online & Nationwide →")));
    };
    render("");

    setPage(town.name + ", " + state.name, [
      breadcrumbs([
        { label: "United States", href: "#/" }, { label: state.name, href: stateHref(state) },
        { label: county.name, href: countyHref(county) }, { label: town.name }]),
      backLink(countyHref(county), "Back to " + county.name),
      h("h1", {}, "Homeschool help in " + town.name + ", " + state.name),
      h("p", { class: "hint" }, "Zip codes: " + town.zips.join(", ")),
      SS.categoryFilter(data, [...local, ...statewide, ...nationwide], render),
      h("div", { class: "two-col" },
        h("section", { "aria-labelledby": "local-heading" },
          h("h2", { id: "local-heading" }, "Local resources"), localCount, localBox),
        h("aside", { class: "also-col side-panel", "aria-labelledby": "also-heading" },
          h("h2", { id: "also-heading" }, "Also available to you"), alsoBox)),
    ]);
  }

  /* ---------- Router ---------- */

  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
    if (parts[0] !== "state" || !parts[1]) return homeView();
    const state = data.stateById[parts[1]];
    if (!state) return comingSoonView(parts[1]);
    if (parts[2] !== "county" || !parts[3]) return stateView(state);
    const county = data.countyByKey[state.id + "/" + parts[3]];
    if (!county) return stateView(state);
    if (parts[4] !== "town" || !parts[5]) return countyView(county);
    const town = data.townByKey[state.id + "/" + parts[5]];
    if (!town || town.county !== county) return countyView(county);
    townView(town);
  }

  Promise.all([SS.loadData(), fetch("data/map.json").then((r) => r.json())])
    .then(([d, g]) => {
      data = d; geo = g;
      route();
      window.addEventListener("hashchange", route);
    })
    .catch((err) => SS.showLoadError(app, err));
})();

/*
  Shared code for every page: mobile menu, loading the sample data,
  listing cards, and the listing detail window.
*/
const SS = (() => {
  /* ---------- Small helpers ---------- */

  // Builds an element. Text is always inserted as text (never as HTML).
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") el.className = value;
      else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
      else el.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  function slugify(text) {
    return String(text).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  // "2026-09-14" -> "Sep 14, 2026" (parsed as a local date, so it never shifts a day).
  function formatDate(iso) {
    if (!iso) return "Not yet checked";
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  /* ---------- Data ---------- */

  let dataPromise;
  function loadData() {
    if (!dataPromise) {
      dataPromise = fetch("data/listings.json")
        .then((res) => {
          if (!res.ok) throw new Error("Could not load data/listings.json (" + res.status + ")");
          return res.json();
        })
        .then(indexData);
    }
    return dataPromise;
  }

  // Adds quick lookups so pages can find states, counties and towns by id.
  function indexData(data) {
    data.categoryById = Object.fromEntries(data.categories.map((c) => [c.id, c]));
    data.stateById = {};
    data.countyByKey = {};
    data.townByKey = {};
    for (const state of data.states) {
      data.stateById[state.id] = state;
      for (const county of state.counties) {
        county.state = state;
        data.countyByKey[state.id + "/" + county.id] = county;
        for (const town of county.towns) {
          town.county = county;
          town.state = state;
          data.townByKey[state.id + "/" + town.id] = town;
        }
      }
    }
    return data;
  }

  const areaTowns = (l) => (l.serviceArea && l.serviceArea.towns) || [];
  const areaCounties = (l) => (l.serviceArea && l.serviceArea.counties) || [];

  function servesTown(listing, town) {
    if (listing.reach !== "Local") return false;
    return areaTowns(listing).includes(town.state.id + "/" + town.id) ||
      areaCounties(listing).includes(town.state.id + "/" + town.county.id);
  }

  function servesCounty(listing, county) {
    if (listing.reach !== "Local") return false;
    const prefix = county.state.id + "/";
    return areaCounties(listing).includes(prefix + county.id) ||
      county.towns.some((t) => areaTowns(listing).includes(prefix + t.id));
  }

  function isStatewideIn(listing, state) {
    return listing.reach === "Statewide" && listing.location && listing.location.state === state.id;
  }

  // Featured listings first, then alphabetical.
  function sortListings(list) {
    return [...list].sort((a, b) => (b.featured - a.featured) || a.name.localeCompare(b.name));
  }

  function categoryName(data, id) {
    return (data.categoryById[id] && data.categoryById[id].name) || id;
  }

  function costText(cost) {
    if (!cost) return "—";
    return cost.type;
  }

  /* ---------- Listing cards ---------- */

  const STATUS_INFO = {
    Verified: { icon: "✓", text: "ShareSchooling confirmed these details with the organizer." },
    Claimed: { icon: "●", text: "The organizer has claimed this listing and keeps it up to date." },
    Unclaimed: { icon: "○", text: "Gathered from public information. The organizer hasn't confirmed it yet." },
  };

  function statusTag(status) {
    const info = STATUS_INFO[status] || { icon: "" };
    return h("span", { class: "tag tag-status-" + String(status).toLowerCase() }, info.icon + " " + status);
  }

  function card(data, listing) {
    const opener = h("button", { type: "button", "aria-haspopup": "dialog" }, listing.name);
    opener.addEventListener("click", () => openDetail(data, listing, opener));
    return h("li", {},
      h("article", { class: "card" + (listing.featured ? " featured" : "") },
        h("div", { class: "tags-top" },
          listing.featured ? h("span", { class: "tag tag-featured" }, "★ Featured") : null,
          h("span", { class: "tag tag-example" }, "Example listing")),
        h("h3", {}, opener),
        h("div", { class: "cat" }, categoryName(data, listing.category)),
        h("dl", {},
          h("dt", {}, "Reach"), h("dd", {}, listing.reach),
          h("dt", {}, "Delivery"), h("dd", {}, listing.delivery),
          h("dt", {}, "Ages"), h("dd", {}, listing.agesGrades ? listing.agesGrades.label : "—"),
          h("dt", {}, "Cost"), h("dd", {}, costText(listing.cost))),
        h("div", { class: "card-foot" },
          statusTag(listing.status),
          h("span", { class: "hint" }, "Checked " + formatDate(listing.lastVerified)))));
  }

  function cardList(data, listings, emptyText, extraClass = "") {
    if (!listings.length) return h("p", { class: "empty-note" }, emptyText);
    return h("ul", { class: "card-grid " + extraClass }, sortListings(listings).map((l) => card(data, l)));
  }

  /* ---------- Listing detail dialog ---------- */

  let dialog, lastOpener;

  function locationText(data, l) {
    if (l.reach === "Nationwide") return "Nationwide";
    const state = l.location && data.stateById[l.location.state];
    if (l.reach === "Statewide") return "Statewide: " + (state ? state.name : "—");
    const town = data.townByKey[l.location.state + "/" + l.location.town];
    return town ? town.name + ", " + town.county.name + ", " + town.state.name : "—";
  }

  function serviceAreaText(data, l) {
    if (l.reach !== "Local") return null;
    const names = [
      ...areaCounties(l).map((k) => data.countyByKey[k] ? "All of " + data.countyByKey[k].name : k),
      ...areaTowns(l).map((k) => data.townByKey[k] ? data.townByKey[k].name : k),
    ];
    return names.join("; ") || "—";
  }

  function openDetail(data, l, opener) {
    lastOpener = opener;
    if (!dialog) {
      dialog = h("dialog", { class: "listing-dialog", "aria-labelledby": "dialog-title" });
      dialog.addEventListener("close", () => lastOpener && lastOpener.focus());
      // Clicking the dark backdrop closes the window.
      dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
      document.body.append(dialog);
    }
    const info = STATUS_INFO[l.status] || { icon: "", text: "" };
    const note = h("p", { class: "inline-note", role: "status" });
    const field = (label, value) => value === null ? [] : [h("dt", {}, label), h("dd", {}, value || "—")];

    dialog.replaceChildren(
      h("button", { type: "button", class: "dialog-close", "aria-label": "Close", onclick: () => dialog.close() }, "×"),
      h("div", { class: "dialog-inner" },
        h("div", { class: "tags-top" },
          l.featured ? h("span", { class: "tag tag-featured" }, "★ Featured") : null,
          h("span", { class: "tag tag-example" }, "Example listing")),
        h("h2", { id: "dialog-title", style: "margin-top:0.5rem" }, l.name),
        h("div", { class: "cat", style: "color:var(--color-accent);font-weight:600" }, categoryName(data, l.category)),
        h("img", { class: "detail-image", src: l.image, alt: "Placeholder photo for " + l.name, width: "320", height: "180" }),
        h("p", {}, l.description),
        h("div", { class: "trust-box" },
          h("span", { class: "icon", "aria-hidden": "true" }, info.icon),
          h("div", {},
            h("strong", {}, l.status), " — " + info.text,
            h("br"), "Last verified: ", h("strong", {}, formatDate(l.lastVerified)))),
        h("dl", { class: "detail-fields" },
          field("Website", l.website ? h("a", { href: l.website, rel: "nofollow noopener", target: "_blank" }, l.website) : ""),
          field("Email", l.email ? h("a", { href: "mailto:" + l.email }, l.email) : ""),
          field("Phone", l.phone),
          field("Who it serves", l.reach),
          field("Location", locationText(data, l)),
          field("Service area", serviceAreaText(data, l)),
          field("Delivery", l.delivery),
          field("Ages / grades", l.agesGrades && l.agesGrades.label),
          field("Subjects", (l.subjects || []).join(", ")),
          field("Approach", l.worldview),
          field("Cost", l.cost ? l.cost.type + (l.cost.note ? " — " + l.cost.note : "") : ""),
          field("Schedule", l.schedule),
          field("Status", l.status),
          field("Last verified", formatDate(l.lastVerified)),
          field("Source", l.source)),
        h("div", { class: "detail-actions" },
          h("a", {
            href: "#", onclick: (e) => {
              e.preventDefault();
              note.textContent = "Thanks! Reporting isn't connected yet — this is a prototype.";
            },
          }, "Report outdated info"),
          h("a", { href: "list-your-resource.html#claim" }, "Claim this listing")),
        note));
    dialog.showModal();
    dialog.querySelector(".dialog-close").focus();
  }

  /* ---------- Category filter ---------- */

  // Renders a category dropdown. Calls onChange(categoryId or "") when it changes.
  function categoryFilter(data, listings, onChange, idSuffix = "") {
    const id = "category-filter" + idSuffix;
    const counts = {};
    for (const l of listings) counts[l.category] = (counts[l.category] || 0) + 1;
    const select = h("select", { id },
      h("option", { value: "" }, "All categories (" + listings.length + ")"),
      data.categories.map((c) => h("option", { value: c.id, disabled: !counts[c.id] },
        c.name + " (" + (counts[c.id] || 0) + ")")));
    select.addEventListener("change", () => onChange(select.value));
    return h("div", { class: "filters" },
      h("div", { class: "field" }, h("label", { for: id }, "Filter by category"), select));
  }

  /* ---------- Page chrome ---------- */

  function initNav() {
    const toggle = document.querySelector(".nav-toggle");
    const nav = document.getElementById("site-nav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  function showLoadError(container, err) {
    container.replaceChildren(h("div", { class: "placeholder-box" },
      h("p", {}, h("strong", {}, "The sample data didn't load. ")),
      h("p", {}, "If you opened this file directly, run a small local web server instead (see README.md). Details: " + err.message)));
  }

  document.addEventListener("DOMContentLoaded", initNav);

  return {
    h, slugify, formatDate, loadData, servesTown, servesCounty, isStatewideIn,
    sortListings, categoryName, card, cardList, categoryFilter, openDetail, showLoadError,
  };
})();

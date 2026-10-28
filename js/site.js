/*
  ShareSchooling site script. Every page is plain HTML built by
  tools/build_site.py; this adds the interactive parts:
  menu, zip search, filters, distance sorting, map toggle and the
  (not yet connected) signup and listing forms.
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

  $$("[data-zip-form]").forEach((form) => {
    const input = $("input", form);
    if (params.get("zip") && !input.value) input.value = params.get("zip");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const status = zipStatusFor(form);
      const zip = input.value.trim();
      if (!/^\d{5}$/.test(zip)) {
        showMessage(status, ["Please enter a 5-digit zip code."]);
        return;
      }
      try {
        const { zips, routes } = await loadZips();
        const hit = zips[zip];
        if (!hit || !routes[hit[0]]) {
          showMessage(status, [
            `We don't have local listings for ${zip} yet. The pilot covers West Tennessee and DeSoto County, MS. Meanwhile, see `,
            link(root + "online.html", "online options"), "."]);
          return;
        }
        location.href = root + routes[hit[0]][0] + "?zip=" + zip;
      } catch (err) {
        showMessage(status, ["Zip search couldn't load. Please try again."]);
      }
    });
  });

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
    const pins = $$("main [data-pin]");

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
      pins.forEach((pin) => { pin.style.display = shown.has(pin.dataset.pin) ? "" : "none"; });
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
      showMessage(status, [`Sorted by distance from ${zip}. Listings without a map location are listed last.`]);
    } catch (err) {
      /* Sorting is a nice-to-have; the list still works without it. */
    }
  }

  /* ---------- Map / list toggle (phones) ---------- */
  const mapToggle = $("[data-map-toggle]");
  if (mapToggle) {
    const area = $("#map-area");
    mapToggle.addEventListener("click", () => {
      area.hidden = !area.hidden;
      mapToggle.setAttribute("aria-expanded", String(!area.hidden));
      mapToggle.textContent = area.hidden ? "Show map" : "Hide map";
    });
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

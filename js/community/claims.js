(function () {
  const SS = window.SS;

  function applyOverlay(overlay) {
    if (!overlay) return;
    const description = document.querySelector("[data-public-description]");
    if (description && overlay.description) description.textContent = overlay.description;
    const mount = document.querySelector("[data-overlay-mount]");
    if (mount) {
      mount.replaceChildren();
      if (overlay.openSpots) mount.append(SS.h("p", {}, [SS.h("strong", {}, "Open spots: "), overlay.openSpots]));
      if (overlay.meetingDays) mount.append(SS.h("p", {}, [SS.h("strong", {}, "Meeting days: "), overlay.meetingDays]));
      if (overlay.updatedLabel) mount.append(SS.h("p", { class: "updated-line" }, overlay.updatedLabel));
    }
    document.querySelectorAll("[data-listing]").forEach((card) => {
      if (!overlay.listingId || card.dataset.id !== overlay.listingId) return;
      const line = card.querySelector("[data-updated]");
      if (line && overlay.updatedLabel) { line.textContent = overlay.updatedLabel; line.hidden = false; }
    });
    const status = document.querySelector("[data-claim-status]");
    if (status && document.querySelector("[data-listing-id]")) {
      /* claim label is applied from the listing payload below */
    }
  }

  function editor(listingId, overlay) {
    const host = document.querySelector("[data-claims-editor]");
    if (!host || !(SS.me && SS.client)) return;
    host.replaceChildren();
    const message = SS.h("p", { class: "form-message", role: "status" });
    const form = SS.h("form", {}, [
      SS.h("p", { class: "muted" }, "Open spots, meeting days, and cost notes publish when you save. A home address in the description waits for a moderator."),
      labeled("Open spots", "openSpots", overlay.openSpots || ""),
      labeled("Meeting days", "meetingDays", overlay.meetingDays || ""),
      labeled("Cost notes", "costNotes", overlay.costNotes || ""),
      labeled("Short description", "description", overlay.description || "", true),
      labeled("Public website", "website", overlay.website || ""),
      labeled("Public email", "email", overlay.email || ""),
      labeled("Public phone", "phone", overlay.phone || ""),
      SS.h("button", { class: "btn", type: "submit" }, "Save"),
      message
    ]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fields = {};
      ["openSpots", "meetingDays", "costNotes", "description", "website", "email", "phone"].forEach((key) => { fields[key] = form.elements[key].value; });
      try {
        await SS.client.saveOverlay(listingId, fields);
        message.textContent = "Saved. If a description looked like an address, the previous public text stays up.";
        setTimeout(() => location.reload(), 500);
      } catch (err) { message.textContent = err.message; }
    });
    host.append(form);
  }

  function labeled(label, name, value, area) {
    const input = area ? SS.h("textarea", { name, rows: "3" }) : SS.h("input", { name, value });
    if (area) input.value = value;
    return SS.h("div", { class: "form-row" }, [SS.h("label", {}, label), input]);
  }

  async function claimFlow() {
    const host = document.querySelector("[data-claim-flow]");
    const note = document.querySelector("[data-claim-note]");
    if (!host || !note || !note.dataset.listingId) return;
    const listingId = note.dataset.listingId;
    const info = (SS.catalog && SS.catalog[listingId]) || { name: listingId, email: "", website: "" };
    note.textContent = "You're claiming " + (info.name || listingId) + ".";
    if (!SS.me) {
      host.append(SS.h("p", {}, [SS.h("a", { href: (document.body.dataset.root || "") + "account/index.html" }, "Sign in"), " to claim this listing."]));
      return;
    }
    const message = SS.h("p", { class: "form-message", role: "status" });
    const form = SS.h("form", { class: "content-card" }, [
      SS.h("label", { class: "check" }, [SS.h("input", { type: "checkbox", name: "represents", required: true }), " I represent this organization."]),
      SS.h("label", {}, "How should we check?"),
      SS.h("select", { name: "method" }, [
        SS.h("option", { value: "manual" }, "Ask an admin to verify"),
        info.email ? SS.h("option", { value: "email" }, "Code to the public email (" + info.email + ")") : null,
        info.website ? SS.h("option", { value: "domain" }, "Code to an email at the website's domain") : null
      ]),
      SS.h("div", { class: "honeypot", "aria-hidden": "true" }, [SS.h("input", { name: "company", tabindex: "-1", autocomplete: "off" })]),
      SS.h("button", { class: "btn", type: "submit" }, "Submit claim"),
      message
    ]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.elements.company.value) return;
      try {
        const result = await SS.client.startClaim({ listingId, represents: true, method: form.elements.method.value, company: "" });
        message.textContent = result.message || "Submitted.";
      } catch (err) { message.textContent = err.message; }
    });
    host.append(form);
  }

  SS.claims = {
    init: async function () {
      const block = document.querySelector("[data-listing-id]");
      if (block) {
        const data = await SS.client.listing(block.dataset.listingId);
        applyOverlay(data.overlay);
        const status = document.querySelector("[data-claim-status]");
        if (status && data.claimLabel) status.textContent = data.claimLabel;
        document.querySelectorAll("[data-updated]").forEach((node) => {
          const card = node.closest("[data-listing]");
          if (card && card.dataset.id === block.dataset.listingId && data.overlay && data.overlay.updatedLabel) {
            node.textContent = data.overlay.updatedLabel;
            node.hidden = false;
          }
        });
        if (data.viewer && data.viewer.canEditListing) editor(block.dataset.listingId, data.overlay || {});
        else {
          const editorHost = document.querySelector("[data-listing-editor]");
          if (editorHost) editorHost.hidden = true;
        }
      }
      const ids = [...document.querySelectorAll("[data-updated]")].map((node) => (node.closest("[data-listing]") || {}).dataset.id).filter(Boolean);
      if (ids.length && SS.client.overlays) {
        try {
          const overlays = await SS.client.overlays(ids);
          overlays.forEach((overlay) => {
            const node = document.querySelector('[data-listing][data-id="' + CSS.escape(overlay.listingId) + '"] [data-updated]');
            if (node && overlay.updatedLabel) { node.textContent = overlay.updatedLabel; node.hidden = false; }
          });
        } catch (err) { /* cards keep the research text */ }
      }
      await claimFlow();
    }
  };
})();

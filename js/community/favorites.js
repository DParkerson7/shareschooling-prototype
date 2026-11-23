(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";
  let savedIds = new Set();

  function paint() {
    document.querySelectorAll("[data-save]").forEach((button) => {
      const card = button.closest("[data-listing]");
      const id = card && card.dataset.id;
      if (!id) return;
      button.hidden = false;
      button.textContent = savedIds.has(id) ? "Saved" : "Save";
      button.onclick = async (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!SS.me) { location.href = root + "account/index.html"; return; }
        if (savedIds.has(id)) { await SS.client.removeFavorite(id); savedIds.delete(id); }
        else { await SS.client.saveFavorite({ listingId: id, alertOnOpenSpots: true }); savedIds.add(id); }
        paint();
      };
    });
    document.querySelectorAll("[data-preview-save]").forEach((node) => {
      node.hidden = false;
      node.replaceChildren(SS.h("button", { type: "button", class: "link-button", onclick: async () => {
        const name = document.querySelector("[data-preview-name]");
        const link = document.querySelector("[data-preview-link]");
        const href = link && link.getAttribute("href") || "";
        const match = href.match(/listing\/([^/]+)\//);
        if (!match) return;
        if (!SS.me) { location.href = root + "account/index.html"; return; }
        await SS.client.saveFavorite({ listingId: match[1], alertOnOpenSpots: true });
        node.textContent = "Saved";
      } }, "Save"));
    });
  }

  SS.favorites = {
    init: async function () {
      if (SS.me) {
        try {
          const data = await SS.client.favorites();
          savedIds = new Set((data.saved || []).map((row) => row.listingId));
          const page = document.querySelector("[data-saved-page]");
          if (page) {
            page.replaceChildren(SS.h("h2", {}, "Since your last visit"));
            if (!(data.changes || []).length) page.append(SS.h("p", { class: "muted" }, "Nothing new. No email was sent."));
            (data.changes || []).forEach((change) => page.append(SS.h("p", {}, (change.name || change.listingId) + (change.kind === "open-spots" ? ": open spots changed to " + (change.after || "cleared") : ": new in " + change.county))));
            page.append(SS.h("h2", {}, "Saved listings"));
            if (!(data.saved || []).length) page.append(SS.h("p", {}, "You haven't saved a listing yet."));
            (data.saved || []).forEach((row) => page.append(SS.h("p", {}, [
              SS.h("a", { href: root + "listing/" + row.listingId + "/" }, row.name || row.listingId),
              " ",
              SS.h("button", { type: "button", class: "link-button", onclick: async () => { await SS.client.removeFavorite(row.listingId); location.reload(); } }, "Remove")
            ])));
          }
        } catch (err) { /* signed out */ }
      }
      paint();
      document.addEventListener("ss-preview-filled", paint);
      const page = document.querySelector("[data-saved-page]");
      if (page && !SS.me) page.append(SS.h("p", {}, [SS.h("a", { href: root + "account/index.html" }, "Sign in"), " to see saved listings."]));
    }
  };
})();

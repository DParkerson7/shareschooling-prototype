(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";
  const cfg = window.SS_CONFIG || {};
  SS.cfg = cfg;
  SS.client = SS.createClient(cfg);

  async function start() {
    try {
      const rows = await fetch(root + "data/community-catalog.json").then((response) => response.json());
      SS.catalog = {};
      rows.forEach((row) => { SS.catalog[row.id] = row; });
    } catch (err) { SS.catalog = {}; }
    let settings;
    try { settings = await SS.client.publicSettings(); }
    catch (err) {
      const note = document.createElement("div");
      note.className = "wake-banner";
      note.textContent = err.message || "The community server didn't respond. The map still works.";
      const banner = document.querySelector(".test-banner");
      if (banner) banner.after(note);
      return;
    }
    SS.settings = settings;
    document.querySelectorAll("[data-module]").forEach((el) => {
      if (settings.modules && settings.modules[el.dataset.module] === false) el.remove();
      else el.hidden = false;
    });
    if (SS.account) await SS.account.init();
    if (SS.reviews && settings.modules.reviews) await SS.reviews.init();
    if (SS.claims && settings.modules.claims) await SS.claims.init();
    if (SS.portal && settings.modules.groupPortal) await SS.portal.init();
    if (SS.looking && settings.modules.lookingFor) await SS.looking.init();
    if (SS.events && settings.modules.events) await SS.events.init();
    if (SS.favorites && settings.modules.favorites) await SS.favorites.init();
    if (SS.admin) await SS.admin.init();
  }
  start();
})();

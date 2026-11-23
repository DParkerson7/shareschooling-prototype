(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";

  function queueItem(item) {
    const card = SS.h("article", { class: "queue-card" }, [
      SS.h("header", {}, [SS.h("strong", {}, item.type), SS.h("span", { class: "muted" }, item.listingName || "")]),
      SS.h("p", {}, item.authorName + (item.approvedReviewCount != null ? " · " + item.approvedReviewCount + " approved reviews" : "")),
      SS.h("p", {}, item.text || ""),
      item.scores && Object.keys(item.scores).length ? SS.h("p", { class: "muted" }, Object.entries(item.scores).map(([key, value]) => {
        const category = ((SS.settings || {}).ratingCategories || []).find((row) => row.id === key);
        return (category ? category.label : key) + " " + value;
      }).join(" · ")) : null,
      SS.h("p", { class: "muted" }, "Reasons: " + ((item.reasons || []).join(", ") || "none") + (item.flagCount ? " · flags " + item.flagCount : ""))
    ]);
    const note = SS.h("p", { class: "form-message", role: "status" });
    const editor = SS.h("textarea", { rows: "3" });
    editor.value = item.text || "";
    card.append(editor, SS.h("div", { class: "queue-actions" }, [
      SS.h("button", { type: "button", class: "btn", onclick: async () => { await SS.client.moderate(item.type, item.id, { action: "approve" }); location.reload(); } }, "Approve"),
      SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => { await SS.client.moderate(item.type, item.id, { action: "edit", body: editor.value }); location.reload(); } }, "Edit and approve"),
      SS.h("button", { type: "button", class: "link-button", onclick: async () => { await SS.client.moderate(item.type, item.id, { action: "remove", note: "Removed in review." }); location.reload(); } }, "Remove")
    ]), note);
    return card;
  }

  async function render(account) {
    const host = document.querySelector("[data-admin-page]");
    if (!host) return;
    host.replaceChildren();
    if (!account) {
      host.append(SS.h("p", {}, [SS.h("a", { href: root + "account/index.html" }, "Sign in"), " with an admin account."]));
      return;
    }
    const staff = (account.roles || []).includes("admin") || (account.roles || []).includes("moderator");
    if (!staff) { host.append(SS.h("p", {}, "You need an admin account.")); return; }
    host.append(SS.h("h2", {}, "Moderation queue"));
    let items = [];
    try { items = await SS.client.queue(); }
    catch (err) { host.append(SS.h("p", {}, err.message)); return; }
    if (!items.length) host.append(SS.h("p", {}, "Nothing is waiting."));
    items.forEach((item) => host.append(queueItem(item)));
    if (!(account.roles || []).includes("admin")) {
      host.append(SS.h("p", {}, "You can work the queue. Settings stay with an admin."));
      return;
    }
    let settings;
    try { settings = await SS.client.adminSettings(); }
    catch (err) { host.append(SS.h("p", {}, err.message)); return; }
    const form = SS.h("form", { class: "content-card" });
    form.append(SS.h("h2", {}, "Settings"));
    form.append(SS.h("p", { class: "muted" }, "All eight modules are on in data/site.json for this review. Turning one off hides it and keeps the rows."));
    const modules = SS.h("fieldset", {}, [SS.h("legend", {}, "Modules")]);
    Object.keys(settings.modules || {}).forEach((key) => {
      const box = SS.h("input", { type: "checkbox", name: "module-" + key });
      box.checked = !!settings.modules[key];
      modules.append(SS.h("label", { class: "check" }, [box, key]));
    });
    const checks = SS.h("fieldset", {}, [SS.h("legend", {}, "Filter")]);
    ["nameCheck", "addressCheck", "harshLanguageCheck", "inviteRequired"].forEach((key) => {
      const box = SS.h("input", { type: "checkbox", name: key });
      box.checked = !!settings[key];
      checks.append(SS.h("label", { class: "check" }, [box, key]));
    });
    const words = SS.h("textarea", { name: "harshWords", rows: "3" });
    words.value = (settings.harshWords || []).join("\n");
    const invite = SS.h("input", { name: "inviteCode", value: settings.inviteCode || "" });
    const numbers = SS.h("div", { class: "settings-grid" });
    ["newAccountHoldCount", "flagsToHide", "trustedBadgeAfter", "lookingForExpireDays"].forEach((key) => {
      numbers.append(SS.h("label", {}, [key, SS.h("input", { name: key, type: "number", value: String(settings[key]) })]));
    });
    const fee = SS.h("input", { name: "portalMonthlyFeeCents", placeholder: "empty", value: settings.portalMonthlyFeeCents == null ? "" : String(settings.portalMonthlyFeeCents) });
    const cut = SS.h("input", { name: "portalDuesCutPercent", placeholder: "empty", value: settings.portalDuesCutPercent == null ? "" : String(settings.portalDuesCutPercent) });
    const message = SS.h("p", { class: "form-message", role: "status" });
    form.append(modules, checks, SS.h("label", {}, ["Harsh words, one per line", words]), SS.h("label", {}, ["Invite code", invite]), numbers);
    form.append(SS.h("p", {}, "Portal price, left empty until you set one. A flat monthly fee (cents) and/or a small cut of dues and class fees. Neither number is invented here."));
    form.append(SS.h("label", {}, ["Monthly fee in cents", fee]), SS.h("label", {}, ["Dues cut percent", cut]));
    form.append(SS.h("button", { class: "btn", type: "submit" }, "Save settings"), message);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const modulesPatch = {};
      Object.keys(settings.modules).forEach((key) => { modulesPatch[key] = form.elements["module-" + key].checked; });
      try {
        await SS.client.updateSettings({
          modules: modulesPatch,
          nameCheck: form.elements.nameCheck.checked,
          addressCheck: form.elements.addressCheck.checked,
          harshLanguageCheck: form.elements.harshLanguageCheck.checked,
          inviteRequired: form.elements.inviteRequired.checked,
          harshWords: words.value,
          inviteCode: invite.value,
          newAccountHoldCount: Number(form.elements.newAccountHoldCount.value),
          flagsToHide: Number(form.elements.flagsToHide.value),
          trustedBadgeAfter: Number(form.elements.trustedBadgeAfter.value),
          lookingForExpireDays: Number(form.elements.lookingForExpireDays.value),
          portalMonthlyFeeCents: fee.value === "" ? null : Number(fee.value),
          portalDuesCutPercent: cut.value === "" ? null : Number(cut.value),
          paymentsMode: "test-only"
        });
        message.textContent = "Saved in this preview." ;
        setTimeout(() => location.reload(), 400);
      } catch (err) { message.textContent = err.message; }
    });
    host.append(form);
    host.append(SS.h("h2", {}, "Accounts"));
    host.append(SS.h("p", { class: "muted" }, "Trusted families are the people the moderator role is for. You can still grant it during the test."));
    let accounts = [];
    try { accounts = await SS.client.accounts(); } catch (err) { accounts = []; }
    accounts.forEach((person) => {
      const row = SS.h("article", { class: "queue-card" }, [
        SS.h("strong", {}, person.displayName),
        SS.h("p", { class: "muted" }, person.email + " · " + (person.roles || []).join(", ") + " · verified " + (person.emailVerified ? "yes" : "no") + " · " + person.approvedReviewCount + " approved")
      ]);
      if (!person.emailVerified) row.append(SS.h("button", { type: "button", class: "btn", onclick: async () => { await SS.client.verifyEmail(person.id); location.reload(); } }, "Mark this email verified"));
      const isMod = (person.roles || []).includes("moderator");
      row.append(SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => { await SS.client.setModerator(person.id, !isMod); location.reload(); } }, isMod ? "Remove moderator" : "Make moderator"));
      host.append(row);
    });
    const grant = SS.h("form", { class: "content-card", onsubmit: async (event) => {
      event.preventDefault();
      try {
        await SS.client.grantPortal(grant.elements.listingId.value.trim(), grant.elements.active.checked);
        alert("Portal updated. This does not change reviews, search, or the map.");
      } catch (err) { alert(err.message); }
    } }, [
      SS.h("h2", {}, "Grant group portal (test)"),
      SS.h("input", { name: "listingId", placeholder: "Listing id", required: true }),
      SS.h("label", { class: "check" }, [SS.h("input", { type: "checkbox", name: "active", checked: true }), "Grant group portal (test)"]),
      SS.h("button", { class: "btn", type: "submit" }, "Save grant")
    ]);
    host.append(grant);
  }

  SS.admin = { init: function () { return render(SS.me); } };
})();

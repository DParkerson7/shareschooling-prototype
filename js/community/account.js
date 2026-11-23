(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";

  function slot(account) {
    const box = document.querySelector("[data-account-slot]");
    if (!box) return;
    box.replaceChildren();
    if (!account) {
      box.append(SS.h("a", { href: root + "account/index.html" }, "Sign in"));
      return;
    }
    box.append(SS.h("span", {}, account.displayName));
    box.append(SS.h("a", { href: root + "account/index.html" }, "Account"));
    if ((account.roles || []).includes("admin") || (account.roles || []).includes("moderator")) {
      box.append(SS.h("a", { href: root + "admin/index.html" }, (account.roles || []).includes("admin") ? "Admin" : "Queue"));
    }
    box.append(SS.h("button", { type: "button", class: "link-button", onclick: async () => { SS.client.logout(); location.reload(); } }, "Sign out"));
  }

  async function current() {
    try { return (await SS.client.me()).account; }
    catch (err) { return null; }
  }

  function field(idName, label, type, name) {
    return SS.h("div", { class: "form-row" }, [
      SS.h("label", { for: idName }, label),
      SS.h("input", { id: idName, name: name, type: type || "text", required: type !== "text" ? true : null })
    ]);
  }

  function renderPage(account) {
    const host = document.querySelector("[data-account-page]");
    if (!host) return;
    host.replaceChildren();
    const demo = SS.cfg && SS.cfg.demo;
    if (demo) {
      host.append(SS.h("p", { class: "confirm-note" }, "Preview only. Sample password is preview. Reset clears this browser tab."));
      host.append(SS.h("div", { class: "sample-accounts" }, [
        ["The Chen family", "chen.family@example.com"],
        ["Alex P. (new)", "new.parent@example.com"],
        ["MHEC board", "board@example.com"],
        ["David (admin)", "david@example.com"]
      ].map(([label, email]) => SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
        await SS.client.login({ email, password: "preview" });
        location.reload();
      } }, label))));
      host.append(SS.h("button", { type: "button", class: "link-button", onclick: () => { SS.client.resetDemo(); location.reload(); } }, "Reset sample data"));
    }
    if (account) {
      host.append(SS.h("p", {}, "Signed in as " + account.displayName + (account.emailVerified ? "." : ". An admin still needs to mark this email verified before you can post.")));
      return;
    }
    const message = SS.h("p", { class: "form-message", role: "status" });
    const login = SS.h("form", { class: "content-card", onsubmit: async (event) => {
      event.preventDefault();
      try {
        await SS.client.login({ email: login.elements.email.value, password: login.elements.password.value });
        location.reload();
      } catch (err) { message.textContent = err.message; }
    } }, [
      SS.h("h2", {}, "Sign in"),
      field("in-email", "Email", "email", "email"),
      field("in-pass", "Password", "password", "password"),
      SS.h("button", { class: "btn", type: "submit" }, "Sign in"),
      message
    ]);
    const note = SS.h("p", { class: "form-message", role: "status" });
    const signup = SS.h("form", { class: "content-card", onsubmit: async (event) => {
      event.preventDefault();
      if (signup.elements.company.value) return;
      try {
        await SS.client.signup({
          email: signup.elements.email.value,
          password: signup.elements.password.value,
          displayName: signup.elements.displayName.value,
          inviteCode: signup.elements.inviteCode.value,
          company: signup.elements.company.value
        });
        note.textContent = "Account created. An admin marks the email verified before you can post. This server does not send mail.";
      } catch (err) { note.textContent = err.message; }
    } }, [
      SS.h("h2", {}, "Create an account"),
      SS.h("p", { class: "muted" }, "Use a family name, or a first name and last initial. Not an email. Not a child's name."),
      field("up-name", "Display name", "text", "displayName"),
      field("up-email", "Email", "email", "email"),
      field("up-pass", "Password", "password", "password"),
      field("up-code", "Invite code", "text", "inviteCode"),
      SS.h("div", { class: "honeypot", "aria-hidden": "true" }, [
        SS.h("label", { for: "up-hp" }, "Leave this empty"),
        SS.h("input", { id: "up-hp", name: "company", tabindex: "-1", autocomplete: "off" })
      ]),
      SS.h("button", { class: "btn", type: "submit" }, "Create account"),
      note
    ]);
    host.append(login, signup);
  }

  SS.account = {
    init: async function () {
      const account = await current();
      SS.me = account;
      slot(account);
      renderPage(account);
    }
  };
})();

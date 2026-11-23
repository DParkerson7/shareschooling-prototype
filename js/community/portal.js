(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";

  function portalLink(listingId) {
    const host = document.querySelector("[data-claims-editor]") || document.querySelector("[data-reviews-root]");
    if (!host || !listingId) return;
    const link = SS.h("p", {}, SS.h("a", { href: root + "portal/index.html?listing=" + encodeURIComponent(listingId) }, "Open group portal (test)"));
    host.before(link);
  }

  async function render(listingId) {
    const host = document.querySelector("[data-portal-page]");
    if (!host) return;
    host.replaceChildren();
    if (!listingId) {
      host.append(SS.h("p", {}, "Open a portal from a listing you represent."));
      const input = SS.h("input", { name: "listing", placeholder: "Listing id" });
      host.append(SS.h("form", { onsubmit: (event) => { event.preventDefault(); location.search = "?listing=" + encodeURIComponent(input.value.trim()); } }, [input, SS.h("button", { class: "btn", type: "submit" }, "Open")]));
      return;
    }
    if (!SS.me) {
      host.append(SS.h("p", {}, [SS.h("a", { href: root + "account/index.html" }, "Sign in"), " to open this group portal."]));
      return;
    }
    let home;
    try { home = await SS.client.portal(listingId); }
    catch (err) {
      host.append(SS.h("p", {}, err.message));
      host.append(SS.h("button", { type: "button", class: "btn", onclick: async () => {
        const result = await SS.client.markPortalPaid(listingId);
        alert(result.message);
        location.reload();
      } }, "Mark as paid (test)"));
      host.append(SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
        try { await SS.client.join(listingId); location.reload(); } catch (joinErr) { alert(joinErr.message); }
      } }, "Join with my email"));
      return;
    }
    host.append(SS.h("p", { class: "trust" }, home.line || "Portal on (test)"));
    host.append(SS.h("h2", {}, home.listingName || "Group"));
    if (home.pricingMessage) host.append(SS.h("p", {}, home.pricingMessage));
    host.append(SS.h("p", { class: "muted" }, "This area is private to the group. It does not change the public listing, the reviews, or the map. Nothing is charged."));
    const roster = SS.h("section", { class: "portal-card" }, [SS.h("h3", {}, "Roster")]);
    (home.roster || []).forEach((person) => roster.append(SS.h("p", {}, person.displayName + " · " + person.role + (person.email ? " · " + person.email : ""))));
    host.append(roster);
    if (home.role === "organizer") {
      const inviteNote = SS.h("p", { class: "form-message", role: "status" });
      const invite = SS.h("form", { class: "portal-card", onsubmit: async (event) => {
        event.preventDefault();
        const result = await SS.client.invite(listingId, invite.elements.email.value);
        inviteNote.textContent = result.message + " Copy it and send it yourself. No email left this site.";
      } }, [
        SS.h("h3", {}, "Invite a member"),
        SS.h("input", { name: "email", type: "email", required: true }),
        SS.h("button", { class: "btn", type: "submit" }, "Make an invite to copy"),
        inviteNote
      ]);
      host.append(invite);
      const offerNote = SS.h("p", { class: "form-message", role: "status" });
      const offer = SS.h("form", { class: "portal-card", onsubmit: async (event) => {
        event.preventDefault();
        await SS.client.addOffering(listingId, {
          kind: offer.elements.kind.value, title: offer.elements.title.value,
          capacity: Number(offer.elements.capacity.value), feeCents: Math.round(Number(offer.elements.dollars.value || 0) * 100)
        });
        location.reload();
      } }, [
        SS.h("h3", {}, "Add a class, trip, or semester"),
        SS.h("select", { name: "kind" }, [SS.h("option", { value: "class" }, "Class"), SS.h("option", { value: "field-trip" }, "Field trip"), SS.h("option", { value: "semester" }, "Semester")]),
        SS.h("input", { name: "title", required: true, placeholder: "Title" }),
        SS.h("input", { name: "capacity", type: "number", min: "1", value: "1" }),
        SS.h("input", { name: "dollars", type: "number", min: "0", step: "0.01", placeholder: "Fee in dollars, 0 if free" }),
        SS.h("button", { class: "btn", type: "submit" }, "Add offering"),
        offerNote
      ]);
      host.append(offer);
    }
    const offers = SS.h("section", { class: "portal-card" }, [SS.h("h3", {}, "Sign-ups")]);
    (home.offerings || []).forEach((offering) => {
      const rows = (home.enrollments || []).filter((row) => row.offeringId === offering.id);
      offers.append(SS.h("p", {}, offering.title + " · " + offering.capacity + " seats · " + (offering.feeCents ? "$" + (offering.feeCents / 100).toFixed(2) + " test fee" : "Free")));
      rows.forEach((row) => offers.append(SS.h("p", { class: "muted" }, (row.state === "waitlist" ? "Waitlist " + row.waitlistPosition : "Enrolled") + " · " + (row.paymentState || ""))));
      offers.append(SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
        try { await SS.client.signupOffering(offering.id); location.reload(); } catch (err) { alert(err.message); }
      } }, "Sign up"));
    });
    (home.enrollments || []).filter((row) => row.accountId === (SS.me && SS.me.id) && row.state !== "dropped").forEach((row) => {
      offers.append(SS.h("button", { type: "button", class: "link-button", onclick: async () => { await SS.client.dropEnrollment(row.id); location.reload(); } }, "Drop my sign-up"));
    });
    host.append(offers);
    const pay = SS.h("section", { class: "portal-card" }, [SS.h("h3", {}, "Test payments")]);
    (home.payments || []).forEach((payment) => {
      pay.append(SS.h("p", {}, (payment.label || payment.kind) + " · " + (payment.paymentState || "") + (payment.summary ? " · " + payment.summary : "")));
      if (payment.paymentState === "due") {
        pay.append(SS.h("button", { type: "button", class: "btn", onclick: async () => {
          const result = await SS.client.markPaid(payment.id);
          alert(result.summary || "Marked as paid (test). Nothing was collected.");
          location.reload();
        } }, "Mark as paid (test)"));
      }
    });
    host.append(pay);
    if (home.role === "organizer") {
      const due = SS.h("form", { class: "portal-card", onsubmit: async (event) => {
        event.preventDefault();
        await SS.client.createDue(listingId, { accountId: due.elements.accountId.value, label: due.elements.label.value || "Dues (test)", amountCents: Math.round(Number(due.elements.dollars.value || 0) * 100) });
        location.reload();
      } }, [
        SS.h("h3", {}, "Record dues (test)"),
        SS.h("select", { name: "accountId" }, (home.roster || []).map((person) => SS.h("option", { value: person.accountId }, person.displayName))),
        SS.h("input", { name: "label", placeholder: "Label" }),
        SS.h("input", { name: "dollars", type: "number", min: "0", step: "0.01", value: "40" }),
        SS.h("button", { class: "btn", type: "submit" }, "Add dues")
      ]);
      host.append(due);
      const ann = SS.h("form", { class: "portal-card", onsubmit: async (event) => {
        event.preventDefault();
        const result = await SS.client.announce(listingId, { title: ann.elements.title.value, body: ann.elements.body.value, audience: "all" });
        alert(result.message);
        location.reload();
      } }, [
        SS.h("h3", {}, "Announcement"),
        SS.h("input", { name: "title", required: true }),
        SS.h("textarea", { name: "body", required: true, rows: "3" }),
        SS.h("button", { class: "btn", type: "submit" }, "Send announcement (test outbox)")
      ]);
      host.append(ann);
      const rot = SS.h("form", { class: "portal-card", onsubmit: async (event) => {
        event.preventDefault();
        try {
          await SS.client.addRotation(listingId, { date: rot.elements.date.value, role: rot.elements.role.value, accountId: rot.elements.accountId.value });
          location.reload();
        } catch (err) { alert(err.message); }
      } }, [
        SS.h("h3", {}, "Rotation"),
        SS.h("input", { name: "date", type: "date", required: true }),
        SS.h("input", { name: "role", value: "Teach", required: true }),
        SS.h("select", { name: "accountId" }, (home.roster || []).map((person) => SS.h("option", { value: person.accountId }, person.displayName))),
        SS.h("button", { class: "btn", type: "submit" }, "Assign a parent")
      ]);
      host.append(rot);
    }
    const messages = SS.h("section", { class: "portal-card" }, [SS.h("h3", {}, "Messages")]);
    if (!(home.messages || []).length) messages.append(SS.h("p", { class: "muted" }, "No announcements in the test outbox."));
    (home.messages || []).forEach((item) => messages.append(SS.h("article", {}, [SS.h("strong", {}, item.title), SS.h("p", {}, item.body || ""), item.waitingMessage ? SS.h("p", {}, item.waitingMessage) : null])));
    host.append(messages);
    const schedule = SS.h("section", { class: "portal-card" }, [SS.h("h3", {}, "Schedule")]);
    (home.rotation || []).forEach((row) => schedule.append(SS.h("p", {}, row.date + " · " + row.role + " · " + (row.displayName || "Parent"))));
    if ((home.children || []).length) {
      schedule.append(SS.h("h3", {}, "Children (private to this portal)"));
      home.children.forEach((child) => schedule.append(SS.h("p", {}, child.firstName + ", grade " + child.grade)));
    }
    const childForm = SS.h("form", { onsubmit: async (event) => {
      event.preventDefault();
      await SS.client.addChild(listingId, { firstName: childForm.elements.firstName.value, grade: childForm.elements.grade.value });
      location.reload();
    } }, [
      SS.h("input", { name: "firstName", placeholder: "Child's first name", required: true }),
      SS.h("input", { name: "grade", placeholder: "Grade", required: true }),
      SS.h("button", { class: "btn btn-secondary", type: "submit" }, "Add a child")
    ]);
    schedule.append(childForm);
    host.append(schedule);
  }

  SS.portal = {
    init: async function () {
      const params = new URLSearchParams(location.search);
      const page = document.querySelector("[data-portal-page]");
      if (page) await render(params.get("listing") || "");
      const listing = document.querySelector("[data-listing-id]");
      if (listing && SS.me) {
        try {
          const data = await SS.client.listing(listing.dataset.listingId);
          if (data.viewer && data.viewer.canOpenPortal) portalLink(listing.dataset.listingId);
          else if (data.viewer && data.viewer.canReply) {
            const host = document.querySelector("[data-reviews-root]");
            if (host) host.append(SS.h("p", {}, SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
              const result = await SS.client.markPortalPaid(listing.dataset.listingId);
              alert(result.message);
              location.href = root + "portal/index.html?listing=" + encodeURIComponent(listing.dataset.listingId);
            } }, "Turn on group portal (test)")));
          }
        } catch (err) { /* the public page still works */ }
      }
    }
  };
})();

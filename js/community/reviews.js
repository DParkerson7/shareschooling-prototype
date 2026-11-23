(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";
  const cache = {};

  function line(summary) {
    if (!summary || !summary.reviewCount) return "";
    const n = summary.reviewCount;
    return n + " family review" + (n === 1 ? "" : "s");
  }
  function averages(summary) {
    const settings = SS.settings || {};
    const labels = {};
    (settings.ratingCategories || []).forEach((category) => { labels[category.id] = SS.shortLabel(category); });
    return Object.entries(summary.averages || {}).map(([key, value]) => (labels[key] || key) + " " + Number(value).toFixed(1)).join(" · ");
  }
  function when(iso) {
    if (!iso) return "";
    const moment = new Date(iso);
    return moment.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  function scoreText(ratings) {
    const settings = SS.settings || {};
    return Object.entries(ratings || {}).map(([key, value]) => {
      const category = (settings.ratingCategories || []).find((row) => row.id === key);
      const label = category ? category.label : key;
      const word = SS.SCORE_LABELS[value - 1] || value;
      return label + ": " + word;
    }).join(" · ");
  }

  function fillCards(summaries) {
    summaries.forEach((summary) => { cache[summary.listingId] = summary; });
    document.querySelectorAll("[data-review-summary]").forEach((node) => {
      const card = node.closest("[data-listing]");
      const summary = card && cache[card.dataset.id];
      node.replaceChildren();
      if (!summary) { node.hidden = true; return; }
      const href = root + "listing/" + summary.listingId + "/#family-reviews";
      node.append(SS.h("a", { href }, line(summary)));
      const extra = averages(summary);
      if (extra) node.append(SS.h("span", { class: "review-averages" }, " " + extra));
      node.hidden = false;
    });
  }

  function fillPreview(id) {
    document.querySelectorAll("[data-preview-reviews]").forEach((node) => {
      const summary = cache[id];
      if (!summary) { node.hidden = true; node.textContent = ""; return; }
      const bits = [summary.reviewCount + " review" + (summary.reviewCount === 1 ? "" : "s")];
      const extra = averages(summary);
      if (extra) bits.push(extra);
      node.textContent = bits.join(" · ");
      node.hidden = false;
    });
  }

  function reviewCard(review) {
    const card = SS.h("article", { class: "review-card" });
    const title = SS.h("header", {}, [
      SS.h("strong", {}, review.authorName || "Family"),
      review.trusted ? SS.h("span", { class: "trust" }, "Trusted family") : null,
      SS.h("span", { class: "muted" }, when(review.publishedAt || review.createdAt))
    ]);
    card.append(title);
    if (review.ratings && Object.keys(review.ratings).length) card.append(SS.h("p", { class: "muted" }, scoreText(review.ratings)));
    if (review.body) card.append(SS.h("p", {}, review.body));
    if (review.waitingMessage) card.append(SS.h("p", { class: "waiting" }, review.waitingMessage));
    if (review.pendingMessage) card.append(SS.h("p", { class: "waiting" }, review.pendingMessage));
    if (review.reply && review.reply.body) {
      card.append(SS.h("div", { class: "reply" }, [
        SS.h("strong", {}, (review.reply.authorName || "The organization") + " replied"),
        SS.h("p", {}, review.reply.body),
        review.reply.pendingMessage ? SS.h("p", { class: "waiting" }, review.reply.pendingMessage) : null,
        review.reply.waitingMessage ? SS.h("p", { class: "waiting" }, review.reply.waitingMessage) : null
      ]));
    }
    const actions = SS.h("div", { class: "queue-actions" });
    if (review.mine && review.status !== "removed") {
      actions.append(SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
        if (!window.confirm("Remove this review?")) return;
        await SS.client.deleteReview(review.id);
        location.reload();
      } }, "Delete"));
    }
    if (SS.me && SS.me.emailVerified && !review.mine && review.status === "published") {
      actions.append(SS.h("button", { type: "button", class: "link-button", onclick: async () => {
        const reason = window.prompt("Why are you flagging this? You can leave it blank.") || "";
        try {
          const result = await SS.client.flag({ targetType: "review", targetId: review.id, reason });
          alert(result.status === "hidden" ? "Flagged. A moderator will look." : "Flagged.");
          if (result.status === "hidden") location.reload();
        } catch (err) { alert(err.message); }
      } }, "Flag"));
    }
    if (actions.childNodes.length) card.append(actions);
    return card;
  }

  function form(listingId, existing) {
    const settings = SS.settings;
    const box = SS.h("form", { class: "content-card" });
    const message = SS.h("p", { class: "form-message", role: "status" });
    box.append(SS.h("h3", {}, existing ? "Edit your review" : "Leave a review"));
    box.append(SS.h("div", { class: "rules" }, [
      SS.h("strong", {}, "Keep it about the group's program."),
      SS.h("ul", {}, SS.RULES.map((rule) => SS.h("li", {}, rule)))
    ]));
    const pickers = SS.h("div", { class: "score-picker" });
    (settings.ratingCategories || []).filter((category) => category.active).forEach((category) => {
      const select = SS.h("select", { name: category.id }, [SS.h("option", { value: "" }, "Skip")].concat(SS.SCORE_LABELS.map((label, index) => {
        const option = SS.h("option", { value: String(index + 1) }, label);
        if (existing && existing.ratings && existing.ratings[category.id] === index + 1) option.selected = true;
        return option;
      })));
      pickers.append(SS.h("div", {}, [SS.h("label", {}, category.label), select]));
    });
    const comment = SS.h("textarea", { name: "body", rows: "4" }, []);
    comment.value = existing && existing.body || "";
    box.append(pickers, SS.h("label", {}, "Comment, if you want one"), comment);
    box.append(SS.h("div", { class: "honeypot", "aria-hidden": "true" }, [SS.h("input", { name: "company", tabindex: "-1", autocomplete: "off" })]));
    box.append(SS.h("button", { class: "btn", type: "submit" }, "Save review"), message);
    box.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (box.elements.company && box.elements.company.value) return;
      const ratings = {};
      (settings.ratingCategories || []).forEach((category) => {
        const value = box.elements[category.id] && box.elements[category.id].value;
        if (value) ratings[category.id] = Number(value);
      });
      try {
        const saved = await SS.client.saveReview({ listingId, ratings, body: comment.value });
        message.textContent = saved.waitingMessage || saved.pendingMessage || "Posted.";
        setTimeout(() => location.reload(), 600);
      } catch (err) { message.textContent = err.message; }
    });
    return box;
  }

  async function renderListing() {
    const section = document.querySelector("[data-reviews-root]");
    const block = document.querySelector("[data-module='reviews']");
    if (!section || !block) return;
    const listingId = block.dataset.listingId;
    const data = await SS.client.listing(listingId, 0);
    if (data.summary) cache[listingId] = data.summary;
    section.replaceChildren();
    if (!data.summary) section.append(SS.h("p", {}, "No family reviews yet."));
    else {
      section.append(SS.h("p", {}, line(data.summary) + (averages(data.summary) ? " · " + averages(data.summary) : "")));
    }
    (data.reviews || []).forEach((review) => section.append(reviewCard(review)));
    if ((data.total || 0) > (data.reviews || []).filter((row) => row.status === "published").length) {
      section.append(SS.h("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
        const more = await SS.client.listing(listingId, (data.reviews || []).length);
        (more.reviews || []).forEach((review) => section.append(reviewCard(review)));
      } }, "Show more"));
    }
    const mine = (data.reviews || []).find((review) => review.mine && review.status !== "removed");
    if (!SS.me) section.append(SS.h("p", {}, ["Sign in to leave a review. ", SS.h("a", { href: root + "account/index.html" }, "Sign in")]));
    else if (SS.me && !SS.me.emailVerified) section.append(SS.h("p", {}, "An admin needs to mark your email verified before you can post."));
    else if (data.viewer && data.viewer.canReply) {
      const replyBox = SS.h("form", { class: "content-card" }, [
        SS.h("h3", {}, mine && mine.reply ? "Edit the organization's reply" : "Reply"),
        SS.h("textarea", { name: "body", rows: "3" })
      ]);
      const note = SS.h("p", { class: "form-message", role: "status" });
      replyBox.append(SS.h("button", { class: "btn", type: "submit" }, "Post reply"), note);
      replyBox.addEventListener("submit", async (event) => {
        event.preventDefault();
        const target = mine || (data.reviews || []).find((review) => review.status === "published");
        if (!target) { note.textContent = "There isn't a public review to reply to."; return; }
        try {
          await SS.client.reply(target.id, replyBox.elements.body.value);
          location.reload();
        } catch (err) { note.textContent = err.message; }
      });
      section.append(replyBox);
    } else if (data.viewer && data.viewer.canReview) section.append(form(listingId, mine));
    else if (SS.me) section.append(SS.h("p", { class: "muted" }, "Sign in with a verified family account to review. An organization doesn't review its own listing."));
  }

  SS.reviews = {
    init: async function () {
      const ids = new Set();
      document.querySelectorAll("[data-listing], [data-result]").forEach((node) => { if (node.dataset.id) ids.add(node.dataset.id); });
      document.querySelectorAll("[data-map-pins]").forEach((node) => {
        try { JSON.parse(node.textContent || "[]").forEach((pin) => ids.add(pin.id)); } catch (err) { /* ignore */ }
      });
      if (ids.size) fillCards(await SS.client.summaries([...ids]));
      document.addEventListener("ss-preview-filled", (event) => fillPreview(event.detail.id));
      await renderListing();
    },
    line, averages
  };
})();

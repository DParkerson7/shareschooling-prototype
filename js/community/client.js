/* Live API client, and the in-browser preview used until communityApi is set. */
(function () {
  const SS = window.SS = window.SS || {};
  const KEY = "ss-demo-v1";
  const USER = "ss-demo-user";

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function nowIso() { return new Date().toISOString().replace(/\.\d{3}Z$/, "Z"); }
  function id(prefix) { return prefix + Math.random().toString(16).slice(2, 10); }
  function byId(rows, itemId) { return (rows || []).find((row) => row.id === itemId); }
  function fail(message) { const err = new Error(message); err.status = 400; throw err; }
  function shortLabel(category) {
    const known = { welcoming: "Welcoming", organized: "Organized", communication: "Communication", "worth-it": "Worth it" };
    return known[category.id] || category.label.split(" ").slice(0, 2).join(" ");
  }
  function listingName(listingId) { return (SS.catalog && SS.catalog[listingId] && SS.catalog[listingId].name) || listingId || ""; }
  function money(cents) { return "$" + (cents / 100).toFixed(2); }
  function feeSplit(cents, percent) {
    if (percent == null || percent === "") return { platformShareCents: null, collected: false, summary: "Test record: " + money(cents) + " dues, platform share not set, not collected." };
    const share = Math.round(cents * Number(percent) / 100);
    return { platformShareCents: share, collected: false, summary: "Test record: " + money(cents) + " dues, " + money(share) + " platform share (not collected), " + money(cents - share) + " to the group." };
  }
  function updatedLabel(isoDate) {
    if (!isoDate) return "";
    const moment = new Date(isoDate + (isoDate.length === 10 ? "T00:00:00Z" : ""));
    return "Updated " + moment.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }

  function loadState() {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (err) { /* start over */ }
    const state = clone(window.SS_DEMO);
    sessionStorage.setItem(KEY, JSON.stringify(state));
    return state;
  }
  function saveState(state) { sessionStorage.setItem(KEY, JSON.stringify(state)); }

  function accountOut(account, settings, withEmail) {
    const trusted = (account.approvedReviewCount || 0) >= Number(settings.trustedBadgeAfter || 3);
    const payload = {
      id: account.id, displayName: account.displayName, emailVerified: !!account.emailVerified,
      roles: account.roles || [], approvedReviewCount: account.approvedReviewCount || 0,
      trusted, createdAt: account.createdAt
    };
    if (withEmail) payload.email = account.email;
    return payload;
  }

  function reviewOut(state, review, viewerId) {
    const settings = state.settings;
    const author = byId(state.accounts, review.authorId);
    const reply = state.replies.find((row) => row.reviewId === review.id);
    const mine = viewerId === review.authorId;
    const showBadge = !!(settings.modules.badges && author && (author.approvedReviewCount || 0) >= Number(settings.trustedBadgeAfter || 3));
    const payload = {
      id: review.id, listingId: review.listingId,
      authorName: author ? author.displayName : "Removed account",
      trusted: showBadge, status: mine ? review.status : "published",
      ratings: review.ratings || {}, body: review.body || "",
      createdAt: review.createdAt, publishedAt: review.publishedAt, mine
    };
    if (mine && review.status === "held") payload.waitingMessage = SS.HELD_MESSAGE;
    if (mine && review.status === "hidden") payload.waitingMessage = "This review is hidden while a moderator looks at flags.";
    if (mine && review.status === "removed") { payload.waitingMessage = "This review was removed."; payload.body = ""; payload.ratings = {}; }
    if (mine && review.pending) payload.pendingMessage = "Your latest edit is waiting. The previous text stays up until a moderator approves it.";
    if (reply && reply.status === "published") {
      const person = byId(state.accounts, reply.authorId);
      payload.reply = { id: reply.id, body: reply.body, createdAt: reply.createdAt, authorName: person ? person.displayName : "The organization", status: "published" };
      if (reply.pending && viewerId === reply.authorId) payload.reply.pendingMessage = "Your latest reply is waiting. The previous text stays up.";
    } else if (reply && viewerId === reply.authorId) {
      payload.reply = { id: reply.id, body: reply.body, status: "held", waitingMessage: SS.HELD_MESSAGE, authorName: "You", createdAt: reply.createdAt };
    }
    return payload;
  }

  function summaryFor(state, listingId) {
    const published = state.reviews.filter((row) => row.listingId === listingId && row.status === "published");
    if (!published.length) return null;
    const averages = {};
    state.settings.ratingCategories.forEach((category) => {
      const values = published.map((row) => row.ratings && row.ratings[category.id]).filter((value) => typeof value === "number");
      if (values.length) averages[category.id] = Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 10) / 10;
    });
    return { listingId, reviewCount: published.length, averages };
  }

  function DemoClient() { this.userId = sessionStorage.getItem(USER) || ""; }
  DemoClient.prototype._state = function () { return loadState(); };
  DemoClient.prototype._save = function (state) { saveState(state); };
  DemoClient.prototype._user = function (state, required) {
    const account = byId(state.accounts, this.userId);
    if (required && !account) fail("Sign in first.");
    return account;
  };
  DemoClient.prototype.logout = function () { this.userId = ""; sessionStorage.removeItem(USER); };
  DemoClient.prototype.resetDemo = function () { sessionStorage.removeItem(KEY); sessionStorage.removeItem(USER); this.userId = ""; };
  DemoClient.prototype._sign = function (account) { this.userId = account.id; sessionStorage.setItem(USER, account.id); };

  DemoClient.prototype.publicSettings = async function () {
    const settings = this._state().settings;
    return {
      demo: true, modules: settings.modules, ratingCategories: settings.ratingCategories,
      inviteRequired: settings.inviteRequired, trustedBadgeAfter: settings.trustedBadgeAfter,
      portalMonthlyFeeCents: settings.portalMonthlyFeeCents, portalDuesCutPercent: settings.portalDuesCutPercent,
      paymentsMode: "test-only", stripeTestConfigured: false, scoreLabels: SS.SCORE_LABELS, rules: SS.RULES
    };
  };
  DemoClient.prototype.summaries = async function (ids) {
    const state = this._state();
    if (!state.settings.modules.reviews) return [];
    return (ids || []).map((listingId) => summaryFor(state, listingId)).filter(Boolean);
  };
  DemoClient.prototype.overlays = async function (ids) {
    const state = this._state();
    if (!state.settings.modules.claims) return [];
    return (ids || []).map((listingId) => {
      const overlay = state.overrides.find((row) => row.listingId === listingId && row.lastUpdated);
      if (!overlay) return null;
      return { listingId, updatedLabel: updatedLabel(overlay.lastUpdated), openSpots: overlay.openSpots || "", meetingDays: overlay.meetingDays || "" };
    }).filter(Boolean);
  };
  DemoClient.prototype.listing = async function (listingId, offset) {
    const state = this._state();
    const settings = state.settings;
    const viewer = this._user(state, false);
    const reviews = state.reviews.filter((row) => row.listingId === listingId);
    const published = reviews.filter((row) => row.status === "published").sort((a, b) => (b.publishedAt || "").localeCompare(a.publishedAt || ""));
    const start = Number(offset || 0);
    let chosen = settings.modules.reviews ? published.slice(start, start + 10) : [];
    if (viewer && settings.modules.reviews) {
      const mine = reviews.find((row) => row.authorId === viewer.id && row.status !== "published");
      if (mine && !chosen.some((row) => row.id === mine.id)) chosen = [mine].concat(chosen);
    }
    const claim = state.claims.find((row) => row.listingId === listingId && row.status === "Verified");
    const mineClaim = viewer && state.claims.find((row) => row.listingId === listingId && row.accountId === viewer.id && row.status === "Verified");
    const overlay = state.overrides.find((row) => row.listingId === listingId && row.lastUpdated);
    const portal = state.portals.find((row) => row.listingId === listingId && row.active);
    const member = viewer && state.members.find((row) => row.listingId === listingId && row.accountId === viewer.id && row.status === "active");
    return {
      summary: settings.modules.reviews ? summaryFor(state, listingId) : null,
      reviews: chosen.map((row) => reviewOut(state, row, viewer && viewer.id)),
      total: settings.modules.reviews ? published.length : 0,
      offset: start,
      overlay: settings.modules.claims && overlay ? {
        listingId, openSpots: overlay.openSpots || "", meetingDays: overlay.meetingDays || "",
        costNotes: overlay.costNotes || "", description: overlay.description || "",
        website: overlay.website || "", email: overlay.email || "", phone: overlay.phone || "",
        lastUpdated: overlay.lastUpdated, updatedLabel: updatedLabel(overlay.lastUpdated)
      } : null,
      claimLabel: settings.modules.claims && claim ? "Claimed by the organization." : null,
      viewer: viewer ? {
        canReview: !!(viewer.emailVerified && !mineClaim && settings.modules.reviews),
        canReply: !!(mineClaim && settings.modules.reviews),
        canEditListing: !!(mineClaim && settings.modules.claims),
        canOpenPortal: !!(settings.modules.groupPortal && portal && (mineClaim || member)),
        saved: !!(settings.modules.favorites && state.favorites.some((row) => row.accountId === viewer.id && row.listingId === listingId))
      } : null
    };
  };

  DemoClient.prototype.signup = async function (body) {
    if (body.company && String(body.company).trim()) return { ok: true };
    const state = this._state();
    const email = String(body.email || "").trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) fail("Enter a valid email address.");
    if (String(body.password || "").length < 8) fail("Use a password of at least 8 characters.");
    const name = String(body.displayName || "").trim();
    if (name.length < 2 || name.includes("@")) fail("Use a family name, or a first name and last initial.");
    if (state.settings.inviteRequired && String(body.inviteCode || "").trim() !== state.settings.inviteCode) fail("That invite code isn't right.");
    if (state.accounts.some((row) => row.email === email)) fail("An account already uses that email.");
    const account = { id: id("acc_"), email, password: body.password, emailVerified: false, displayName: name, roles: ["family"], approvedReviewCount: 0, createdAt: nowIso() };
    state.accounts.push(account);
    this._save(state);
    this._sign(account);
    return { ok: true, account: accountOut(account, state.settings, true) };
  };
  DemoClient.prototype.login = async function (body) {
    const state = this._state();
    const email = String(body.email || "").trim().toLowerCase();
    const account = state.accounts.find((row) => row.email === email && row.password === body.password);
    if (!account) fail("That email or password isn't right.");
    this._sign(account);
    return { ok: true, account: accountOut(account, state.settings, true) };
  };
  DemoClient.prototype.me = async function () {
    const state = this._state();
    const account = this._user(state, true);
    return { account: accountOut(account, state.settings, true) };
  };

  DemoClient.prototype.saveReview = async function (body) {
    const state = this._state();
    const account = this._user(state, true);
    if (!state.settings.modules.reviews) fail("That part of the site is turned off.");
    if (!account.emailVerified) fail("Confirm your email first. On this test, an admin marks it verified.");
    if (state.claims.some((row) => row.accountId === account.id && row.listingId === body.listingId && row.status === "Verified")) fail("An organization doesn't review its own listing.");
    const ratings = body.ratings || {};
    const scored = Object.entries(ratings).filter(([, value]) => value);
    if (!scored.length) fail("Choose at least one category score.");
    const text = body.body || "";
    const org = listingName(body.listingId);
    let reasons = SS.withNewAccount(SS.filterText(text, state.settings, org), account, state.settings);
    let review = state.reviews.find((row) => row.listingId === body.listingId && row.authorId === account.id);
    if (!review) {
      review = { id: id("rev_"), listingId: body.listingId, authorId: account.id, createdAt: nowIso(), counted: false, flagCount: 0 };
      state.reviews.push(review);
    }
    if (review.status === "hidden") fail("This review is hidden while a moderator looks at it.");
    if (review.status === "published" && reasons.length) {
      review.pending = { ratings, body: text, holdReasons: reasons };
    } else {
      review.ratings = ratings; review.body = text; review.pending = null; review.holdReasons = reasons;
      review.status = reasons.length ? "held" : "published";
      if (!reasons.length) {
        review.publishedAt = review.publishedAt || nowIso();
        if (!review.counted) { account.approvedReviewCount = (account.approvedReviewCount || 0) + 1; review.counted = true; }
      }
    }
    this._save(state);
    const out = reviewOut(state, review, account.id);
    out.holdReasons = review.holdReasons || [];
    return out;
  };
  DemoClient.prototype.deleteReview = async function (reviewId) {
    const state = this._state();
    const account = this._user(state, true);
    const review = byId(state.reviews, reviewId);
    if (!review || review.authorId !== account.id) fail("That review isn't yours.");
    review.status = "removed"; review.pending = null;
    this._save(state);
    return { ok: true };
  };
  DemoClient.prototype.flag = async function (body) {
    const state = this._state();
    const account = this._user(state, true);
    if (!account.emailVerified) fail("Confirm your email first. On this test, an admin marks it verified.");
    const collection = { review: "reviews", looking: "looking", event: "events" }[body.targetType];
    const target = byId(state[collection] || [], body.targetId);
    if (!target) fail("That post isn't here.");
    if (target.authorId === account.id) fail("You can't flag your own post.");
    if (state.flags.some((row) => row.targetType === body.targetType && row.targetId === body.targetId && row.authorId === account.id)) {
      return { ok: true, counted: false, flagCount: target.flagCount || 0, status: target.status };
    }
    if (target.status !== "published") fail("Only a live post can be flagged.");
    state.flags.push({ id: id("flag_"), targetType: body.targetType, targetId: body.targetId, authorId: account.id, reason: body.reason || "", createdAt: nowIso() });
    target.flagCount = (target.flagCount || 0) + 1;
    if (target.flagCount >= Number(state.settings.flagsToHide || 3)) target.status = "hidden";
    this._save(state);
    return { ok: true, counted: true, flagCount: target.flagCount, status: target.status };
  };
  DemoClient.prototype.reply = async function (reviewId, text) {
    const state = this._state();
    const account = this._user(state, true);
    const review = byId(state.reviews, reviewId);
    if (!review || review.status !== "published") fail("You can reply once a review is public.");
    const claim = state.claims.find((row) => row.accountId === account.id && row.listingId === review.listingId && row.status === "Verified");
    if (!claim) fail("Only the verified organization can reply.");
    const body = String(text || "").trim();
    if (!body) fail("Write a reply first.");
    const reasons = SS.filterText(body, state.settings, listingName(review.listingId));
    let reply = state.replies.find((row) => row.reviewId === reviewId);
    if (!reply) {
      reply = { id: id("reply_"), reviewId, listingId: review.listingId, authorId: account.id, createdAt: nowIso(), body: "", status: "held" };
      state.replies.push(reply);
    }
    if (reasons.length && reply.status === "published") reply.pending = { body, holdReasons: reasons };
    else { reply.body = body; reply.pending = null; reply.status = reasons.length ? "held" : "published"; reply.holdReasons = reasons; }
    this._save(state);
    return reviewOut(state, review, account.id);
  };

  DemoClient.prototype.startClaim = async function (body) {
    if (body.company && String(body.company).trim()) return { ok: true };
    if (!body.represents) fail("Confirm that you represent this organization.");
    const state = this._state();
    const account = this._user(state, true);
    if (!account.emailVerified) fail("Confirm your email first. On this test, an admin marks it verified.");
    let claim = state.claims.find((row) => row.listingId === body.listingId && (row.status === "Claimed" || row.status === "Verified"));
    if (claim && claim.accountId !== account.id) fail("Someone has already asked to represent this listing.");
    if (claim && claim.status === "Verified") return { ok: true, status: "Verified", id: claim.id, message: "This listing is already verified for your account." };
    const code = body.method === "manual" ? "" : String(Math.floor(Math.random() * 1000000)).padStart(6, "0");
    if (!claim) { claim = { id: id("claim_"), listingId: body.listingId, accountId: account.id, createdAt: nowIso() }; state.claims.push(claim); }
    claim.status = "Claimed"; claim.method = body.method || "manual"; claim.codePlain = code;
    this._save(state);
    return { ok: true, id: claim.id, status: "Claimed", mailed: false, message: "This preview can't send mail. The code is in the admin queue, or mark the claim verified there." };
  };
  DemoClient.prototype.saveOverlay = async function (listingId, fields) {
    const state = this._state();
    const account = this._user(state, true);
    if (!state.settings.modules.claims) fail("That part of the site is turned off.");
    const claim = state.claims.find((row) => row.accountId === account.id && row.listingId === listingId && row.status === "Verified");
    if (!claim) fail("Only the verified organization can edit this listing.");
    let overlay = state.overrides.find((row) => row.listingId === listingId);
    if (!overlay) { overlay = { id: listingId, listingId, pending: null }; state.overrides.push(overlay); }
    ["openSpots", "meetingDays", "costNotes"].forEach((key) => { if (key in fields) overlay[key] = fields[key] || ""; });
    overlay.pending = overlay.pending || {};
    ["description", "website", "email", "phone"].forEach((key) => {
      if (!(key in fields)) return;
      const reasons = SS.filterText(fields[key] || "", state.settings, "");
      if (reasons.length) overlay.pending[key] = { value: fields[key], reasons };
      else { overlay[key] = fields[key] || ""; delete overlay.pending[key]; }
    });
    if (!Object.keys(overlay.pending).length) overlay.pending = null;
    overlay.lastUpdated = new Date().toISOString().slice(0, 10);
    overlay.updatedBy = account.id;
    this._save(state);
    return { overlay: { ...overlay, updatedLabel: updatedLabel(overlay.lastUpdated), pending: undefined } };
  };

  DemoClient.prototype.queue = async function () {
    const state = this._state();
    const account = this._user(state, true);
    if (!(account.roles || []).some((role) => role === "admin" || role === "moderator")) fail("You need an admin account.");
    const items = [];
    const add = (type, row, text, reasons) => {
      const author = byId(state.accounts, row.authorId || row.accountId || row.updatedBy);
      items.push({
        type, id: row.id, listingId: row.listingId || "", listingName: listingName(row.listingId),
        authorName: author ? author.displayName : "", approvedReviewCount: author ? author.approvedReviewCount : 0,
        text: text || "", scores: row.ratings || {}, reasons: reasons || row.holdReasons || [],
        flagCount: row.flagCount || 0, createdAt: row.createdAt || row.lastUpdated || ""
      });
    };
    state.reviews.forEach((row) => {
      if (row.status === "held" || row.status === "hidden") add("review", row, row.body, row.holdReasons);
      if (row.pending) add("review-edit", row, row.pending.body, row.pending.holdReasons);
    });
    state.replies.forEach((row) => { if (row.status === "held") add("reply", row, row.body, row.holdReasons); });
    state.claims.forEach((row) => { if (row.status === "Claimed") add("claim", row, (row.codePlain ? "Code " + row.codePlain + ". Mail was not sent." : "Waiting for an admin to mark it verified."), ["claim"]); });
    state.overrides.forEach((row) => { if (row.pending) add("overlay", row, Object.entries(row.pending).map(([key, value]) => key + ": " + value.value).join("\n"), [].concat(...Object.values(row.pending).map((value) => value.reasons || []))); });
    state.looking.forEach((row) => { if (row.status === "held" || row.status === "hidden") add("looking", row, row.title + "\n" + row.body, row.holdReasons); });
    state.events.forEach((row) => { if (row.status === "held" || row.status === "hidden") add("event", row, row.title + "\n" + row.summary, row.holdReasons); });
    state.announcements.forEach((row) => { if (row.status === "held") add("announcement", row, row.title + "\n" + row.body, row.holdReasons); });
    return items;
  };
  DemoClient.prototype.moderate = async function (kind, itemId, body) {
    const state = this._state();
    const account = this._user(state, true);
    if (!(account.roles || []).includes("admin") && !(account.roles || []).includes("moderator")) fail("You need an admin account.");
    const action = body.action;
    if (kind === "review" || kind === "review-edit") {
      const review = byId(state.reviews, itemId);
      if (!review) fail("That review isn't in the queue.");
      if (action === "remove") { review.status = "removed"; review.pending = null; }
      else {
        if (action === "edit") { review.body = body.body || review.body; if (body.ratings) review.ratings = body.ratings; review.pending = null; }
        else if (review.pending && kind === "review-edit") { review.body = review.pending.body; review.ratings = review.pending.ratings; review.pending = null; }
        review.status = "published"; review.holdReasons = []; review.publishedAt = review.publishedAt || nowIso();
        if (!review.counted) {
          const author = byId(state.accounts, review.authorId);
          if (author) author.approvedReviewCount = (author.approvedReviewCount || 0) + 1;
          review.counted = true;
        }
        review.flagCount = 0;
      }
    } else if (kind === "claim") {
      const claim = byId(state.claims, itemId);
      if (!claim) fail("That claim isn't in the queue.");
      if (action === "remove") claim.status = "Rejected";
      else {
        claim.status = "Verified"; claim.codePlain = "";
        const person = byId(state.accounts, claim.accountId);
        if (person && !(person.roles || []).includes("organization")) person.roles.push("organization");
      }
    } else if (kind === "reply") {
      const reply = byId(state.replies, itemId);
      if (reply) { if (action === "remove") reply.status = "removed"; else { if (action === "edit") reply.body = body.body || reply.body; reply.status = "published"; } }
    } else if (kind === "overlay") {
      const overlay = byId(state.overrides, itemId);
      if (overlay && overlay.pending) {
        if (action !== "remove") Object.entries(overlay.pending).forEach(([key, value]) => { overlay[key] = action === "edit" && body.body && key === "description" ? body.body : value.value; });
        overlay.pending = null;
      }
    } else {
      ["looking", "events", "announcements"].forEach((name) => {
        const row = byId(state[name] || [], itemId);
        if (row) row.status = action === "remove" ? "removed" : (name === "announcements" ? "outbox" : "published");
      });
    }
    this._save(state);
    return { ok: true };
  };

  DemoClient.prototype.adminSettings = async function () {
    const state = this._state();
    const account = this._user(state, true);
    if (!(account.roles || []).includes("admin")) fail("You need an admin account.");
    return state.settings;
  };
  DemoClient.prototype.updateSettings = async function (patch) {
    const state = this._state();
    const account = this._user(state, true);
    if (!(account.roles || []).includes("admin")) fail("You need an admin account.");
    const settings = state.settings;
    if (patch.modules) Object.keys(patch.modules).forEach((key) => { if (key in settings.modules) settings.modules[key] = !!patch.modules[key]; });
    ["nameCheck", "addressCheck", "harshLanguageCheck", "inviteRequired"].forEach((key) => { if (key in patch) settings[key] = !!patch[key]; });
    ["newAccountHoldCount", "flagsToHide", "trustedBadgeAfter", "lookingForExpireDays"].forEach((key) => { if (key in patch) settings[key] = Number(patch[key]); });
    if ("harshWords" in patch) settings.harshWords = Array.isArray(patch.harshWords) ? patch.harshWords : String(patch.harshWords || "").split(/\n|,/).map((word) => word.trim()).filter(Boolean);
    if ("inviteCode" in patch && String(patch.inviteCode || "").trim()) settings.inviteCode = String(patch.inviteCode).trim();
    if ("ratingCategories" in patch) settings.ratingCategories = patch.ratingCategories;
    if ("portalMonthlyFeeCents" in patch) settings.portalMonthlyFeeCents = patch.portalMonthlyFeeCents === "" ? null : patch.portalMonthlyFeeCents;
    if ("portalDuesCutPercent" in patch) settings.portalDuesCutPercent = patch.portalDuesCutPercent === "" ? null : patch.portalDuesCutPercent;
    if (patch.paymentsMode && patch.paymentsMode !== "test-only") fail("Payments stay in test mode. Live charges are not part of this build.");
    this._save(state);
    return settings;
  };
  DemoClient.prototype.accounts = async function () {
    const state = this._state();
    const account = this._user(state, true);
    if (!(account.roles || []).includes("admin")) fail("You need an admin account.");
    return state.accounts.map((row) => accountOut(row, state.settings, true));
  };
  DemoClient.prototype.verifyEmail = async function (accountId) {
    const state = this._state();
    const admin = this._user(state, true);
    if (!(admin.roles || []).includes("admin")) fail("You need an admin account.");
    const account = byId(state.accounts, accountId);
    if (!account) fail("That account isn't here.");
    account.emailVerified = true;
    this._save(state);
    return accountOut(account, state.settings, true);
  };
  DemoClient.prototype.setModerator = async function (accountId, grant) {
    const state = this._state();
    const admin = this._user(state, true);
    if (!(admin.roles || []).includes("admin")) fail("You need an admin account.");
    const account = byId(state.accounts, accountId);
    account.roles = (account.roles || []).filter((role) => role !== "moderator");
    if (grant) account.roles.push("moderator");
    this._save(state);
    const trusted = (account.approvedReviewCount || 0) >= Number(state.settings.trustedBadgeAfter || 3);
    return Object.assign(accountOut(account, state.settings, true), { note: trusted ? "" : "Trusted families are the people this is for." });
  };
  DemoClient.prototype.grantPortal = async function (listingId, active) {
    const state = this._state();
    const admin = this._user(state, true);
    if (!(admin.roles || []).includes("admin")) fail("You need an admin account.");
    if (!state.settings.modules.groupPortal) fail("That part of the site is turned off.");
    const claim = state.claims.find((row) => row.listingId === listingId && row.status === "Verified");
    if (!claim) fail("Verify a claim before granting the group portal.");
    let portal = state.portals.find((row) => row.listingId === listingId);
    if (!portal) { portal = { id: listingId, listingId, publicBadge: false }; state.portals.push(portal); }
    portal.active = !!active; portal.source = "admin-grant"; portal.grantedBy = admin.id; portal.publicBadge = false;
    if (active) ensureMember(state, listingId, claim.accountId, "organizer");
    this._save(state);
    return { active: portal.active, publicBadge: false, source: portal.source };
  };

  function ensureMember(state, listingId, accountId, role) {
    let member = state.members.find((row) => row.listingId === listingId && row.accountId === accountId);
    if (!member) { member = { id: listingId + ":" + accountId, listingId, accountId, role, status: "active" }; state.members.push(member); }
    member.status = "active";
    if (role === "organizer") member.role = "organizer";
    return member;
  }
  function requireMember(state, account, listingId) {
    if (!state.settings.modules.groupPortal) fail("That part of the site is turned off.");
    const portal = state.portals.find((row) => row.listingId === listingId && row.active);
    if (!portal) fail("This group portal is off.");
    const member = state.members.find((row) => row.listingId === listingId && row.accountId === account.id && row.status === "active");
    if (!member) fail("You aren't a member of this group.");
    return { portal, member };
  }

  DemoClient.prototype.markPortalPaid = async function (listingId) {
    const state = this._state();
    const account = this._user(state, true);
    const claim = state.claims.find((row) => row.accountId === account.id && row.listingId === listingId && row.status === "Verified");
    if (!claim) fail("Only the verified organization can turn the portal on.");
    let portal = state.portals.find((row) => row.listingId === listingId);
    if (!portal) { portal = { id: listingId, listingId, publicBadge: false }; state.portals.push(portal); }
    portal.active = true; portal.source = "mark-as-paid"; portal.publicBadge = false;
    ensureMember(state, listingId, account.id, "organizer");
    this._save(state);
    const price = state.settings.portalMonthlyFeeCents;
    return { ok: true, charged: false, message: price == null ? "Pricing isn't set yet. This test won't charge you." : "Marked as paid (test). Nothing was charged." };
  };
  DemoClient.prototype.portal = async function (listingId) {
    const state = this._state();
    const account = this._user(state, true);
    const { portal, member } = requireMember(state, account, listingId);
    const organizer = member.role === "organizer";
    const roster = state.members.filter((row) => row.listingId === listingId && row.status === "active").map((row) => {
      const person = byId(state.accounts, row.accountId) || {};
      const item = { accountId: row.accountId, role: row.role, displayName: person.displayName || "" };
      if (organizer) item.email = person.email || "";
      return item;
    });
    const children = state.children.filter((row) => row.listingId === listingId && (organizer || row.accountId === account.id)).map((row) => ({ id: row.id, accountId: row.accountId, firstName: row.firstName, grade: row.grade }));
    const messages = state.deliveries.filter((row) => row.accountId === account.id && row.listingId === listingId).map((row) => byId(state.announcements, row.announcementId)).filter((row) => row && row.status === "outbox");
    if (organizer) state.announcements.filter((row) => row.listingId === listingId && row.status === "held").forEach((row) => messages.push(Object.assign({ waitingMessage: SS.HELD_MESSAGE }, row)));
    return {
      listingId, listingName: listingName(listingId), line: "Portal on (test)", role: member.role,
      source: portal.source, publicBadge: false,
      pricingMessage: state.settings.portalMonthlyFeeCents == null ? "Pricing isn't set yet. This test won't charge you." : "",
      roster, children, offerings: state.offerings.filter((row) => row.listingId === listingId),
      enrollments: state.enrollments.filter((row) => row.listingId === listingId && row.state !== "dropped" && (organizer || row.accountId === account.id)),
      payments: state.payments.filter((row) => row.listingId === listingId && (organizer || row.accountId === account.id)),
      messages, rotation: state.rotation.filter((row) => row.listingId === listingId).map((row) => Object.assign({ displayName: (byId(state.accounts, row.accountId) || {}).displayName || "" }, row)),
      invites: organizer ? state.invites.filter((row) => row.listingId === listingId).map((row) => row.email) : []
    };
  };
  DemoClient.prototype.invite = async function (listingId, email) {
    const state = this._state();
    const account = this._user(state, true);
    const access = requireMember(state, account, listingId);
    if (access.member.role !== "organizer") fail("Only an organizer can do that.");
    const address = String(email || "").trim().toLowerCase();
    if (!state.invites.some((row) => row.listingId === listingId && row.email === address)) state.invites.push({ id: id("inv_"), listingId, email: address });
    this._save(state);
    return { ok: true, emailed: false, email: address, message: "You're invited to the " + listingName(listingId) + " group portal on ShareSchooling (a test). Sign in with " + address + " and open the group. Nothing is charged in this test." };
  };
  DemoClient.prototype.join = async function (listingId) {
    const state = this._state();
    const account = this._user(state, true);
    const invite = state.invites.find((row) => row.listingId === listingId && row.email === account.email);
    if (!invite && !state.members.some((row) => row.listingId === listingId && row.accountId === account.id)) fail("There's no invite for this email.");
    ensureMember(state, listingId, account.id, "member");
    state.invites = state.invites.filter((row) => row !== invite);
    this._save(state);
    return { ok: true };
  };
  DemoClient.prototype.addChild = async function (listingId, body) {
    const state = this._state();
    const account = this._user(state, true);
    requireMember(state, account, listingId);
    const first = String(body.firstName || "").trim();
    if (!first || first.includes("@")) fail("Use the child's first name only.");
    const child = { id: id("child_"), accountId: account.id, listingId, firstName: first, grade: String(body.grade || "").trim(), private: true };
    state.children.push(child);
    this._save(state);
    return child;
  };
  DemoClient.prototype.addOffering = async function (listingId, body) {
    const state = this._state();
    const account = this._user(state, true);
    const access = requireMember(state, account, listingId);
    if (access.member.role !== "organizer") fail("Only an organizer can do that.");
    const offering = { id: id("off_"), listingId, kind: body.kind || "class", title: body.title, capacity: Number(body.capacity || 1), feeCents: Number(body.feeCents || 0), startsOn: body.startsOn || "", endsOn: body.endsOn || "" };
    state.offerings.push(offering);
    this._save(state);
    return offering;
  };
  DemoClient.prototype.signupOffering = async function (offeringId, childId) {
    const state = this._state();
    const account = this._user(state, true);
    const offering = byId(state.offerings, offeringId);
    requireMember(state, account, offering.listingId);
    if (state.enrollments.some((row) => row.offeringId === offeringId && row.accountId === account.id && row.state !== "dropped")) fail("You're already signed up for that.");
    const enrolled = state.enrollments.filter((row) => row.offeringId === offeringId && row.state === "enrolled");
    const row = { id: id("enr_"), offeringId, listingId: offering.listingId, accountId: account.id, childId: childId || "", createdAt: nowIso() };
    if (enrolled.length < offering.capacity) {
      row.state = "enrolled"; row.paymentState = offering.feeCents ? "due" : "not-required";
      if (offering.feeCents) state.payments.push({ id: id("pay_"), listingId: offering.listingId, accountId: account.id, kind: "class-fee", label: offering.title, amountCents: offering.feeCents, enrollmentId: row.id, paymentState: "due", collected: false, summary: "" });
    } else {
      const waiting = state.enrollments.filter((item) => item.offeringId === offeringId && item.state === "waitlist");
      row.state = "waitlist"; row.waitlistPosition = waiting.length + 1; row.paymentState = "not-required";
    }
    state.enrollments.push(row);
    this._save(state);
    return row;
  };
  DemoClient.prototype.dropEnrollment = async function (enrollmentId) {
    const state = this._state();
    const account = this._user(state, true);
    const enrollment = byId(state.enrollments, enrollmentId);
    if (!enrollment) fail("That sign-up isn't here.");
    enrollment.state = "dropped";
    const offering = byId(state.offerings, enrollment.offeringId);
    let promoted = null;
    const enrolled = state.enrollments.filter((row) => row.offeringId === offering.id && row.state === "enrolled");
    const waiting = state.enrollments.filter((row) => row.offeringId === offering.id && row.state === "waitlist").sort((a, b) => (a.waitlistPosition || 0) - (b.waitlistPosition || 0));
    if (enrolled.length < offering.capacity && waiting.length) {
      const next = waiting[0];
      next.state = "enrolled"; next.waitlistPosition = null; next.paymentState = offering.feeCents ? "due" : "not-required";
      if (offering.feeCents) state.payments.push({ id: id("pay_"), listingId: offering.listingId, accountId: next.accountId, kind: "class-fee", label: offering.title, amountCents: offering.feeCents, enrollmentId: next.id, paymentState: "due", collected: false, summary: "" });
      promoted = { accountId: next.accountId, paymentState: next.paymentState, message: "You're in." };
    }
    this._save(state);
    return { ok: true, promoted };
  };
  DemoClient.prototype.createDue = async function (listingId, body) {
    const state = this._state();
    const account = this._user(state, true);
    const access = requireMember(state, account, listingId);
    if (access.member.role !== "organizer") fail("Only an organizer can do that.");
    const payment = { id: id("pay_"), listingId, accountId: body.accountId, kind: "dues", label: body.label || "Dues (test)", amountCents: Number(body.amountCents || 0), paymentState: "due", collected: false, summary: "", createdAt: nowIso() };
    state.payments.push(payment);
    this._save(state);
    return payment;
  };
  DemoClient.prototype.markPaid = async function (paymentId) {
    const state = this._state();
    this._user(state, true);
    const payment = byId(state.payments, paymentId);
    if (!payment) fail("That payment isn't here.");
    const split = feeSplit(payment.amountCents, state.settings.portalDuesCutPercent);
    payment.paymentState = "paid-test"; payment.method = "mark-as-paid"; payment.collected = false;
    payment.platformShareCents = split.platformShareCents; payment.summary = split.summary;
    this._save(state);
    return payment;
  };
  DemoClient.prototype.announce = async function (listingId, body) {
    const state = this._state();
    const account = this._user(state, true);
    const access = requireMember(state, account, listingId);
    if (access.member.role !== "organizer") fail("Only an organizer can do that.");
    const reasons = SS.filterFields([body.title, body.body], state.settings, listingName(listingId));
    const announcement = { id: id("ann_"), listingId, title: body.title, body: body.body, audience: body.audience || "all", status: reasons.length ? "held" : "outbox", holdReasons: reasons, authorId: account.id, createdAt: nowIso() };
    state.announcements.push(announcement);
    if (!reasons.length) state.members.filter((row) => row.listingId === listingId && row.status === "active").forEach((member) => state.deliveries.push({ id: announcement.id + ":" + member.accountId, announcementId: announcement.id, accountId: member.accountId, listingId }));
    this._save(state);
    return { id: announcement.id, status: announcement.status, emailed: false, message: reasons.length ? "Held for a person to check." : "Saved in the test outbox. No email was sent." };
  };
  DemoClient.prototype.addRotation = async function (listingId, body) {
    const state = this._state();
    const account = this._user(state, true);
    const access = requireMember(state, account, listingId);
    if (access.member.role !== "organizer") fail("Only an organizer can do that.");
    if (String(body.accountId || "").startsWith("child_") || byId(state.children, body.accountId)) fail("Assign a parent, not a child.");
    const row = { id: id("rot_"), listingId, date: body.date, role: body.role, accountId: body.accountId };
    state.rotation.push(row);
    this._save(state);
    return row;
  };

  DemoClient.prototype.looking = async function (stateCode, county) {
    const state = this._state();
    if (!state.settings.modules.lookingFor) return [];
    const now = Date.now();
    return state.looking.filter((row) => row.status === "published" && (!row.expiresAt || Date.parse(row.expiresAt) > now) && (!stateCode || row.state === stateCode) && (!county || row.county === county)).map((row) => Object.assign({
      authorName: (byId(state.accounts, row.authorId) || {}).displayName || "",
      replies: state.lookingReplies.filter((reply) => reply.postId === row.id && reply.status === "published").map((reply) => ({ id: reply.id, body: reply.body, authorName: (byId(state.accounts, reply.authorId) || {}).displayName || "", status: "published" }))
    }, row));
  };
  DemoClient.prototype.saveLooking = async function (body) {
    const state = this._state();
    const account = this._user(state, true);
    if (!account.emailVerified) fail("Confirm your email first. On this test, an admin marks it verified.");
    const reasons = SS.withNewAccount(SS.filterFields([body.title, body.body], state.settings, ""), account, state.settings);
    const row = { id: id("need_"), authorId: account.id, title: body.title, body: body.body, category: body.category || "", state: body.state, county: body.county, city: body.city || "", status: reasons.length ? "held" : "published", holdReasons: reasons, createdAt: nowIso(), expiresAt: new Date(Date.now() + (state.settings.lookingForExpireDays || 90) * 86400000).toISOString() };
    state.looking.push(row);
    this._save(state);
    return Object.assign({ waitingMessage: reasons.length ? SS.HELD_MESSAGE : "" }, row);
  };
  DemoClient.prototype.replyLooking = async function (postId, text) {
    const state = this._state();
    const account = this._user(state, true);
    const reasons = SS.filterText(text, state.settings, "");
    const reply = { id: id("lrep_"), postId, authorId: account.id, body: text, status: reasons.length ? "held" : "published", holdReasons: reasons, createdAt: nowIso() };
    state.lookingReplies.push(reply);
    this._save(state);
    return reply;
  };
  DemoClient.prototype.events = async function (stateCode, county) {
    const state = this._state();
    if (!state.settings.modules.events) return [];
    const now = Date.now();
    return state.events.filter((row) => row.status === "published" && (!row.endsAt || Date.parse(row.endsAt) >= now) && (!stateCode || row.state === stateCode) && (!county || row.county === county)).map((row) => Object.assign({ pinned: !!(row.listingId && SS.catalog && SS.catalog[row.listingId]) }, row));
  };
  DemoClient.prototype.saveEvent = async function (body) {
    const state = this._state();
    const account = this._user(state, true);
    const reasons = SS.withNewAccount(SS.filterFields([body.title, body.summary], state.settings, ""), account, state.settings);
    if (SS.filterText(body.venue || "", Object.assign({}, state.settings, { nameCheck: false }), "").length) reasons.push("address");
    const row = { id: id("evt_"), authorId: account.id, listingId: body.listingId || "", title: body.title, summary: body.summary, venue: body.venue, startsAt: body.startsAt, endsAt: body.endsAt, state: body.state, county: body.county, city: body.city || "", status: reasons.length ? "held" : "published", holdReasons: reasons, createdAt: nowIso() };
    state.events.push(row);
    this._save(state);
    return Object.assign({ waitingMessage: reasons.length ? SS.HELD_MESSAGE : "", pinned: !!row.listingId }, row);
  };
  DemoClient.prototype.favorites = async function () {
    const state = this._state();
    const account = this._user(state, true);
    if (!state.settings.modules.favorites) return { saved: [], changes: [], emailed: false };
    const saved = [];
    const changes = [];
    state.favorites.filter((row) => row.accountId === account.id).forEach((row) => {
      const overlay = state.overrides.find((item) => item.listingId === row.listingId);
      const current = state.settings.modules.claims && overlay ? (overlay.openSpots || "") : null;
      if (row.seenOpenSpots == null) row.seenOpenSpots = current;
      else if (row.alertOnOpenSpots && current != null && current !== row.seenOpenSpots) {
        changes.push({ listingId: row.listingId, name: listingName(row.listingId), kind: "open-spots", before: row.seenOpenSpots || "", after: current });
        row.seenOpenSpots = current;
      }
      saved.push({ listingId: row.listingId, name: listingName(row.listingId), savedAt: row.savedAt, alertOnOpenSpots: !!row.alertOnOpenSpots });
    });
    this._save(state);
    return { saved, changes, emailed: false };
  };
  DemoClient.prototype.saveFavorite = async function (body) {
    const state = this._state();
    const account = this._user(state, true);
    const favoriteId = account.id + ":" + body.listingId;
    let row = byId(state.favorites, favoriteId);
    if (!row) { row = { id: favoriteId, accountId: account.id, listingId: body.listingId, savedAt: nowIso(), seenOpenSpots: null }; state.favorites.push(row); }
    row.alertOnOpenSpots = !!body.alertOnOpenSpots;
    this._save(state);
    return { ok: true, saved: true };
  };
  DemoClient.prototype.removeFavorite = async function (listingId) {
    const state = this._state();
    const account = this._user(state, true);
    state.favorites = state.favorites.filter((row) => !(row.accountId === account.id && row.listingId === listingId));
    this._save(state);
    return { ok: true, saved: false };
  };

  function LiveClient(api) { this.api = String(api || "").replace(/\/$/, ""); }
  LiveClient.prototype.request = async function (method, path, body) {
    const run = async (timeout) => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeout);
      try {
        const headers = { "Content-Type": "application/json" };
        const token = localStorage.getItem("ss-token");
        if (token) headers.Authorization = "Bearer " + token;
        const response = await fetch(this.api + path, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) fail(data.error || "The community server didn't respond.");
        return data;
      } finally { clearTimeout(timer); }
    };
    try { return await run(8000); }
    catch (err) {
      if (err.status) throw err;
      if (SS.waking) SS.waking(true);
      try { return await run(60000); }
      finally { if (SS.waking) SS.waking(false); }
    }
  };
  const liveMap = {
    publicSettings: ["GET", "/api/public/settings"],
    summaries: ["GET", (ids) => "/api/public/summaries?ids=" + encodeURIComponent((ids || []).join(",")), true],
    listing: ["GET", (listingId, offset) => "/api/public/listings/" + encodeURIComponent(listingId) + "?offset=" + (offset || 0), true],
    signup: ["POST", "/api/auth/signup"],
    login: ["POST", "/api/auth/login"],
    me: ["GET", "/api/auth/me"],
    saveReview: ["POST", "/api/reviews"],
    flag: ["POST", "/api/flags"],
    queue: ["GET", "/api/admin/queue"],
    adminSettings: ["GET", "/api/admin/settings"],
    updateSettings: ["PATCH", "/api/admin/settings"],
    accounts: ["GET", "/api/admin/accounts"],
    looking: ["GET", (stateCode, county) => "/api/public/looking-for?state=" + encodeURIComponent(stateCode || "") + "&county=" + encodeURIComponent(county || ""), true],
    events: ["GET", (stateCode, county) => "/api/public/events?state=" + encodeURIComponent(stateCode || "") + "&county=" + encodeURIComponent(county || ""), true],
    favorites: ["GET", "/api/favorites"],
    saveLooking: ["POST", "/api/looking-for"],
    saveEvent: ["POST", "/api/events"],
    saveFavorite: ["POST", "/api/favorites"]
  };
  Object.keys(liveMap).forEach((name) => {
    const spec = liveMap[name];
    LiveClient.prototype[name] = async function (...args) {
      const path = spec[2] ? spec[1](...args) : spec[1];
      const body = spec[2] ? undefined : args[0];
      const data = await this.request(spec[0], path, spec[0] === "GET" ? undefined : body);
      if (name === "summaries") return data.summaries || [];
      if (name === "looking") return data.posts || [];
      if (name === "events") return data.events || [];
      if (name === "queue") return data.items || [];
      if (name === "accounts") return data.accounts || [];
      if (name === "login" || name === "signup") {
        if (data.token) localStorage.setItem("ss-token", data.token);
      }
      return data;
    };
  });
  LiveClient.prototype.logout = function () { localStorage.removeItem("ss-token"); };
  LiveClient.prototype.resetDemo = function () {};
  LiveClient.prototype.overlays = async function (ids) {
    const data = await this.request("GET", "/api/public/overlays?ids=" + encodeURIComponent((ids || []).join(",")));
    return data.overlays || [];
  };
  LiveClient.prototype.deleteReview = function (reviewId) { return this.request("DELETE", "/api/reviews/" + reviewId); };
  LiveClient.prototype.reply = function (reviewId, text) { return this.request("POST", "/api/reviews/" + reviewId + "/reply", { body: text }); };
  LiveClient.prototype.startClaim = function (body) { return this.request("POST", "/api/claims", body); };
  LiveClient.prototype.saveOverlay = function (listingId, body) { return this.request("PATCH", "/api/listings/" + listingId + "/overlay", body); };
  LiveClient.prototype.moderate = function (kind, itemId, body) { return this.request("POST", "/api/admin/queue/" + kind + "/" + itemId, body); };
  LiveClient.prototype.verifyEmail = function (accountId) { return this.request("POST", "/api/admin/accounts/" + accountId + "/verify-email", {}); };
  LiveClient.prototype.setModerator = function (accountId, grant) { return this.request("POST", "/api/admin/accounts/" + accountId + "/moderator", { grant }); };
  LiveClient.prototype.grantPortal = function (listingId, active) { return this.request("POST", "/api/admin/portals/" + listingId, { active }); };
  LiveClient.prototype.portal = function (listingId) { return this.request("GET", "/api/portal/" + listingId); };
  LiveClient.prototype.markPortalPaid = function (listingId) { return this.request("POST", "/api/portal/" + listingId + "/mark-paid", {}); };
  LiveClient.prototype.invite = function (listingId, email) { return this.request("POST", "/api/portal/" + listingId + "/invites", { email }); };
  LiveClient.prototype.join = function (listingId) { return this.request("POST", "/api/portal/" + listingId + "/join", {}); };
  LiveClient.prototype.addChild = function (listingId, body) { return this.request("POST", "/api/portal/" + listingId + "/children", body); };
  LiveClient.prototype.addOffering = function (listingId, body) { return this.request("POST", "/api/portal/" + listingId + "/offerings", body); };
  LiveClient.prototype.signupOffering = function (offeringId, childId) { return this.request("POST", "/api/portal/offerings/" + offeringId + "/signup", { childId }); };
  LiveClient.prototype.dropEnrollment = function (enrollmentId) { return this.request("POST", "/api/portal/enrollments/" + enrollmentId + "/drop", {}); };
  LiveClient.prototype.createDue = function (listingId, body) { return this.request("POST", "/api/portal/" + listingId + "/dues", body); };
  LiveClient.prototype.markPaid = function (paymentId) { return this.request("POST", "/api/portal/payments/" + paymentId + "/mark-paid", {}); };
  LiveClient.prototype.announce = function (listingId, body) { return this.request("POST", "/api/portal/" + listingId + "/announcements", body); };
  LiveClient.prototype.addRotation = function (listingId, body) { return this.request("POST", "/api/portal/" + listingId + "/rotation", body); };
  LiveClient.prototype.replyLooking = function (postId, text) { return this.request("POST", "/api/looking-for/" + postId + "/replies", { body: text }); };
  LiveClient.prototype.removeFavorite = function (listingId) { return this.request("DELETE", "/api/favorites/" + listingId); };

  SS.shortLabel = shortLabel;
  SS.updatedLabel = updatedLabel;
  SS.createClient = function (cfg) { return cfg && cfg.api ? new LiveClient(cfg.api) : new DemoClient(); };
  SS.h = function (tag, props, kids) {
    const node = document.createElement(tag);
    Object.entries(props || {}).forEach(([key, value]) => {
      if (value == null || value === false) return;
      if (key === "class") node.className = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
      else node.setAttribute(key, value === true ? "" : value);
    });
    [].concat(kids || []).forEach((kid) => {
      if (kid == null || kid === false) return;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    });
    return node;
  };
  SS.waking = function (on) {
    let note = document.querySelector("[data-waking]");
    if (on && !note) {
      note = SS.h("div", { class: "wake-banner", "data-waking": "1", role: "status" }, "Waking the server… the free service sleeps after about 15 minutes.");
      const banner = document.querySelector(".demo-banner, .test-banner");
      if (banner) banner.after(note);
    }
    if (!on && note) note.remove();
  };
})();

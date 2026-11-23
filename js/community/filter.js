/* Keep this in step with api/logic.py. A low score is not a hold reason. */
(function (root) {
  const SS = root.SS = root.SS || {};
  const STOP = new Set("the a an and or in on at to for of by we our their this that these those new west east north south my his her its monday tuesday wednesday thursday friday saturday sunday".split(" "));
  const street = /\b\d{1,6}\s+(?:[A-Za-z0-9.'#-]+\s+){0,5}(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|court|ct|way|circle|cir|parkway|pkwy|trail|trl|highway|hwy)\b/i;
  const email = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i;
  const phone = /(?<!\d)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\d)|\b\d{3}[\s.-]\d{4}\b/;
  const child = /\bmy\s+(?:son|daughter|child|kid)\s+[A-Za-z][a-z]{1,20}\b/i;
  const two = /\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})\b/g;

  function words(text) {
    return new Set((String(text || "").match(/[A-Za-z0-9']+/g) || []).map((part) => part.toLowerCase()));
  }

  SS.filterText = function (text, settings, orgName) {
    const reasons = [];
    const body = text || "";
    if (!String(body).trim()) return reasons;
    const prefs = settings || {};
    if (prefs.addressCheck !== false) {
      if (street.test(body)) reasons.push("address");
      if (email.test(body)) reasons.push("email");
      if (phone.test(body)) reasons.push("phone");
    }
    if (prefs.nameCheck !== false) {
      if (child.test(body)) reasons.push("possible-name");
      else {
        const tokens = words(orgName);
        const flat = String(orgName || "").toLowerCase();
        two.lastIndex = 0;
        let match;
        while ((match = two.exec(body))) {
          if (STOP.has(match[1].toLowerCase())) continue;
          const phrase = (match[1] + " " + match[2]).toLowerCase();
          if (flat.includes(phrase)) continue;
          if (tokens.has(match[1].toLowerCase()) && tokens.has(match[2].toLowerCase())) continue;
          reasons.push("possible-name");
          break;
        }
      }
    }
    if (prefs.harshLanguageCheck !== false) {
      for (const word of prefs.harshWords || []) {
        const cleaned = String(word || "").trim();
        if (!cleaned) continue;
        const pattern = new RegExp("\\b" + cleaned.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
        if (pattern.test(body)) { reasons.push("harsh-language"); break; }
      }
    }
    return reasons;
  };

  SS.filterFields = function (parts, settings, orgName) {
    const reasons = [];
    (parts || []).forEach((part) => {
      SS.filterText(part, settings, orgName).forEach((reason) => {
        if (!reasons.includes(reason)) reasons.push(reason);
      });
    });
    return reasons;
  };

  SS.withNewAccount = function (reasons, account, settings) {
    const out = reasons.slice();
    const limit = Number((settings || {}).newAccountHoldCount ?? 2);
    if ((account.approvedReviewCount || 0) < limit && !out.includes("new-account")) out.push("new-account");
    return out;
  };

  SS.HELD_MESSAGE = "A moderator will look at this before it appears. New accounts wait for the first couple of reviews. A review also waits if it may include a name, an address, or harsh wording. A low rating is not a reason to wait.";
  SS.RULES = ["Don't include children's names.", "Don't include home addresses, personal phone numbers, or personal emails.", "Fair criticism is welcome. A low rating is posted like any other review.", "Personal attacks aren't allowed."];
  SS.SCORE_LABELS = ["Poor", "Fair", "Good", "Very good", "Excellent"];
})(typeof window !== "undefined" ? window : globalThis);

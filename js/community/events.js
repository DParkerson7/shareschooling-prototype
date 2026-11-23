(function () {
  const SS = window.SS;
  function when(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  function draw(detail, events) {
    if (!detail || !detail.layer || !events.length) return;
    const pins = detail.pins || [];
    events.filter((event) => event.listingId && event.status !== "held").forEach((event) => {
      const pin = pins.find((item) => item.id === event.listingId);
      if (!pin) return;
      const px = detail.px;
      const size = px(7);
      const x = pin.x + px(16);
      const y = pin.y - px(16);
      const mark = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      mark.setAttribute("points", [x, y - size, x + size, y, x, y + size, x - size, y].join(" "));
      mark.setAttribute("class", "event-mark");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = event.title + " (event, not a permanent listing)";
      mark.append(title);
      detail.layer.append(mark);
    });
  }
  SS.events = {
    init: async function () {
      const stateCode = (document.body.dataset.state || "").toUpperCase();
      const county = document.body.dataset.county || "";
      const host = document.querySelector("[data-events]");
      let events = [];
      if (host || document.querySelector("[data-map]")) events = await SS.client.events(stateCode, county);
      if (host) {
        host.replaceChildren(SS.h("h2", {}, "Coming up"));
        if (!events.length) host.append(SS.h("p", { class: "muted" }, "No upcoming events."));
        events.forEach((event) => host.append(SS.h("article", { class: "post-card" }, [
          SS.h("strong", {}, event.title),
          SS.h("p", { class: "muted" }, when(event.startsAt) + (event.venue ? " · " + event.venue : "")),
          SS.h("p", {}, event.summary || "")
        ])));
        if (SS.me && SS.me.emailVerified) {
          const form = SS.h("form", { class: "content-card", onsubmit: async (event) => {
            event.preventDefault();
            const saved = await SS.client.saveEvent({
              title: form.elements.title.value, summary: form.elements.summary.value, venue: form.elements.venue.value,
              startsAt: new Date(form.elements.start.value).toISOString(), endsAt: new Date(form.elements.end.value).toISOString(),
              state: stateCode, county, listingId: form.elements.listingId.value
            });
            alert(saved.waitingMessage || "Added.");
            location.reload();
          } }, [
            SS.h("h3", {}, "Add an event"),
            SS.h("input", { name: "title", required: true, placeholder: "Title" }),
            SS.h("textarea", { name: "summary", required: true, rows: "2", placeholder: "Public place only. No home address." }),
            SS.h("input", { name: "venue", required: true, placeholder: "Public venue" }),
            SS.h("input", { name: "start", type: "datetime-local", required: true }),
            SS.h("input", { name: "end", type: "datetime-local", required: true }),
            SS.h("input", { name: "listingId", placeholder: "Listing id, optional" }),
            SS.h("button", { class: "btn", type: "submit" }, "Add event")
          ]);
          host.append(form);
        }
      }
      document.addEventListener("ss-map-rendered", (event) => draw(event.detail, events));
      document.querySelectorAll("[data-map]").forEach((stage) => { if (stage._community) draw(stage._community, events); });
    }
  };
})();

(function () {
  const SS = window.SS;
  const root = document.body.dataset.root || "";

  function card(post) {
    return SS.h("article", { class: "post-card" }, [
      SS.h("header", {}, [SS.h("strong", {}, post.title), SS.h("span", { class: "muted" }, [post.city, post.county, post.state].filter(Boolean).join(", "))]),
      SS.h("p", {}, post.body || ""),
      SS.h("p", { class: "muted" }, post.authorName || ""),
      post.waitingMessage ? SS.h("p", {}, post.waitingMessage) : null
    ].concat((post.replies || []).map((reply) => SS.h("div", { class: "reply" }, [SS.h("strong", {}, reply.authorName || "Reply"), SS.h("p", {}, reply.body)]))));
  }

  function form(stateCode, county) {
    if (!SS.me) return SS.h("p", {}, [SS.h("a", { href: root + "account/index.html" }, "Sign in"), " to post."]);
    const message = SS.h("p", { class: "form-message", role: "status" });
    const node = SS.h("form", { class: "content-card", onsubmit: async (event) => {
      event.preventDefault();
      try {
        const saved = await SS.client.saveLooking({
          title: node.elements.title.value, body: node.elements.body.value,
          state: node.elements.state.value || stateCode, county: node.elements.county.value || county,
          city: node.elements.city.value, category: node.elements.category.value
        });
        message.textContent = saved.waitingMessage || "Posted.";
        setTimeout(() => location.reload(), 500);
      } catch (err) { message.textContent = err.message; }
    } }, [
      SS.h("h3", {}, "Post a need"),
      SS.h("input", { name: "title", required: true, placeholder: "What you need" }),
      SS.h("textarea", { name: "body", required: true, rows: "3" }),
      SS.h("input", { name: "state", value: stateCode || "", placeholder: "State" }),
      SS.h("input", { name: "county", value: county || "", placeholder: "County" }),
      SS.h("input", { name: "city", placeholder: "City (optional)" }),
      SS.h("input", { name: "category", placeholder: "Category id, optional" }),
      SS.h("button", { class: "btn", type: "submit" }, "Post"),
      message
    ]);
    return node;
  }

  SS.looking = {
    init: async function () {
      const countyHost = document.querySelector("[data-looking-for]");
      const pageHost = document.querySelector("[data-looking-page]");
      const stateCode = (document.body.dataset.state || "").toUpperCase();
      const county = document.body.dataset.county || "";
      if (countyHost) {
        const posts = await SS.client.looking(stateCode, county);
        countyHost.replaceChildren(SS.h("h2", {}, "Families here are looking for"));
        if (!posts.length) countyHost.append(SS.h("p", { class: "muted" }, "Nothing posted for this county yet."));
        posts.slice(0, 5).forEach((post) => countyHost.append(card(post)));
        countyHost.append(SS.h("p", {}, SS.h("a", { href: root + "looking-for/index.html" }, "See all")));
      }
      if (pageHost) {
        const params = new URLSearchParams(location.search);
        const posts = await SS.client.looking(params.get("state") || "", params.get("county") || "");
        pageHost.replaceChildren(form(params.get("state") || "", params.get("county") || ""));
        if (!posts.length) pageHost.append(SS.h("p", {}, "No posts yet."));
        posts.forEach((post) => {
          const item = card(post);
          if (SS.me && SS.me.emailVerified) {
            const reply = SS.h("form", { onsubmit: async (event) => {
              event.preventDefault();
              await SS.client.replyLooking(post.id, reply.elements.body.value);
              location.reload();
            } }, [SS.h("input", { name: "body", placeholder: "Reply", required: true }), SS.h("button", { class: "btn btn-secondary", type: "submit" }, "Reply")]);
            item.append(reply);
          }
          pageHost.append(item);
        });
      }
    }
  };
})();

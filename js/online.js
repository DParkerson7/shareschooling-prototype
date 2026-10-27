// Online & Nationwide: browse by subject, grade or category, without the map.
(() => {
  const { h } = SS;
  const root = document.getElementById("online-app");

  const GRADES = [[-1, "PreK"], [0, "Kindergarten"], ...Array.from({ length: 12 }, (_, i) => [i + 1, "Grade " + (i + 1)])];

  SS.loadData().then((data) => {
    // Nationwide listings, plus any listing that is delivered online.
    const listings = data.listings.filter((l) => l.reach === "Nationwide" || l.delivery === "Online");
    const subjects = [...new Set(listings.flatMap((l) => l.subjects || []))].sort();

    const subjectSel = h("select", { id: "f-subject" }, h("option", { value: "" }, "Any subject"), subjects.map((s) => h("option", { value: s }, s)));
    const gradeSel = h("select", { id: "f-grade" }, h("option", { value: "" }, "Any grade"), GRADES.map(([v, t]) => h("option", { value: v }, t)));
    const catSel = h("select", { id: "f-cat" }, h("option", { value: "" }, "All categories"),
      data.categories.map((c) => h("option", { value: c.id }, c.name)));
    const reachSel = h("select", { id: "f-reach" }, h("option", { value: "" }, "Nationwide and statewide online"),
      h("option", { value: "Nationwide" }, "Nationwide only"));
    const count = h("p", { class: "results-count", "aria-live": "polite" });
    const results = h("div", {});

    function render() {
      const grade = gradeSel.value === "" ? null : Number(gradeSel.value);
      const shown = listings.filter((l) =>
        (!subjectSel.value || (l.subjects || []).includes(subjectSel.value)) &&
        (!catSel.value || l.category === catSel.value) &&
        (!reachSel.value || l.reach === reachSel.value) &&
        (grade === null || (l.agesGrades && l.agesGrades.min !== null && l.agesGrades.min <= grade && grade <= l.agesGrades.max)));
      count.textContent = "Showing " + shown.length + " of " + listings.length + " listings";
      results.replaceChildren(SS.cardList(data, shown, "No listings match these choices yet. Try widening your filters."));
    }
    [subjectSel, gradeSel, catSel, reachSel].forEach((s) => s.addEventListener("change", render));

    const field = (id, label, sel) => h("div", { class: "field" }, h("label", { for: id }, label), sel);
    root.replaceChildren(
      h("div", { class: "filters", role: "group", "aria-label": "Filters" },
        field("f-subject", "Subject", subjectSel),
        field("f-grade", "Grade", gradeSel),
        field("f-cat", "Category", catSel),
        field("f-reach", "Show", reachSel)),
      count, results);
    render();
  }).catch((err) => SS.showLoadError(root, err));
})();

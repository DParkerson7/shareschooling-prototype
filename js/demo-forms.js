// Prototype forms: nothing is saved or sent. Submitting just shows a note.
document.querySelectorAll("form.demo-form").forEach((form) => {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    form.querySelector('[role="status"]').textContent =
      "Thanks! This form isn't connected yet — it's part of the prototype, so nothing was sent.";
  });
});

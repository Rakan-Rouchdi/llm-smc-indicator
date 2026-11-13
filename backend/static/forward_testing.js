"use strict";
document.querySelectorAll(".review-form").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    const status = form.querySelector('[role="status"]');
    const fields = new FormData(form);
    button.disabled = true;
    status.textContent = "Saving...";
    try {
      const response = await fetch(`/forward-testing/decisions/${form.dataset.decisionId}/reviews`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({outcome: fields.get("outcome"), entry_status: fields.get("entry_status"),
          observed_until: new Date(fields.get("observed_until")).toISOString(),
          source_verified: fields.has("source_verified"), notes: fields.get("notes")})
      });
      const result = await response.json();
      if (!response.ok) {
        status.textContent = typeof result.detail === "string" ? result.detail :
          "Review not saved. Check the observation time, evidence, source confirmation and entry status.";
        button.disabled = false;
        return;
      }
      window.location.reload();
    } catch {
      status.textContent = "Save status unknown. Reload and check audit history before submitting again.";
    }
  });
});

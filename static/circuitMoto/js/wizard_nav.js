// static/circuitMoto/js/wizard_nav.js
(function () {
  function ensureHidden(form, name, value) {
    let input = form.querySelector(`input[name="${name}"]`);
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      form.appendChild(input);
    }
    input.value = value;
  }

  function getWizardMode() {
    const body = document.body;
    const mode = body && body.getAttribute("data-wizard-mode");
    if (mode) return mode;

    const saveBtn = document.querySelector('button[name="wizard_action"][value="save"]');
    return saveBtn ? "edit" : "create";
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".step-link[data-wizard-step]");
    if (!btn) return;

    e.preventDefault();

    const stepName = btn.getAttribute("data-wizard-step");
    const stepUrl = btn.getAttribute("data-step-url");
    if (!stepName) return;

    const mode = getWizardMode();

    // ✅ EDIT : navigation GET
    if (mode === "edit") {
      if (stepUrl) {
        window.location.href = stepUrl;
        return;
      }
      // fallback (rare)
      const parts = window.location.pathname.split("/").filter(Boolean);
      if (parts.length) {
        parts[parts.length - 1] = stepName;
        window.location.href = "/" + parts.join("/") + "/";
      }
      return;
    }

    // ✅ CREATE : POST wizard_goto_step
    const form = document.querySelector("form.form-step");
    if (!form) return;

    ensureHidden(form, "wizard_goto_step", stepName);
    form.submit();
  });
})();

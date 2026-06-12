// static/circuitMoto/js/balades_1_jour.js
document.addEventListener("DOMContentLoaded", function () {
  const tsInput = document.querySelector('input[name="ts"]');
  if (tsInput) {
    tsInput.value = String(Math.floor(Date.now() / 1000));
  }

  const form = document.querySelector(".b1j-form");
  if (!form) return;

  const checkboxes = Array.from(form.querySelectorAll('.b1j-cards input[type="checkbox"]'));
  const liveCounter = document.getElementById("b1jLiveCounter");
  const selectionCount = document.getElementById("b1jSelectionCount");
  const selectionPlural = document.getElementById("b1jSelectionPlural");
  const selectionHint = document.getElementById("b1jSelectionHint");
  const asideCount = document.getElementById("b1jAsideCount");
  const asideText = document.getElementById("b1jAsideText");
  const submitBtn = document.getElementById("b1jSubmitBtn");
  const submitText = document.getElementById("b1jSubmitText");

  let isSubmitting = false;

  function selectedCount() {
    return checkboxes.filter((cb) => cb.checked).length;
  }

  function setSubmitLocked(locked) {
    if (!submitBtn) return;

    submitBtn.disabled = locked;
    submitBtn.classList.toggle("is-submitting", locked);
    submitBtn.setAttribute("aria-busy", locked ? "true" : "false");

    if (locked) {
      submitBtn.dataset.originalText = submitText ? submitText.textContent : "";
      if (submitText) {
        const count = selectedCount();
        submitText.textContent = count > 0
          ? `Envoi en cours (${count})...`
          : "Envoi en cours...";
      }
    } else {
      if (submitText) {
        const original = submitBtn.dataset.originalText || "Recevoir les programmes sélectionnés";
        submitText.textContent = original;
      }
    }
  }

  function updateSelectionUI() {
    const checked = selectedCount();

    checkboxes.forEach((cb) => {
      const card = cb.closest(".b1j-card");
      if (!card) return;
      card.classList.toggle("is-selected", cb.checked);
    });

    if (liveCounter) {
      liveCounter.textContent = `${checked} sélectionnée${checked > 1 ? "s" : ""}`;
    }

    if (selectionCount) {
      selectionCount.textContent = String(checked);
    }

    if (selectionPlural) {
      selectionPlural.textContent = checked > 1 ? "s" : "";
    }

    if (selectionHint) {
      if (checked === 0) {
        selectionHint.textContent = "Cochez une ou plusieurs balades";
      } else if (checked === 1) {
        selectionHint.textContent = "1 balade choisie, vous pouvez continuer ou en ajouter d’autres";
      } else {
        selectionHint.textContent = `${checked} balades choisies, parfait pour recevoir plusieurs programmes`;
      }
    }

    if (asideCount) {
      asideCount.textContent = String(checked);
    }

    if (asideText) {
      if (checked === 0) {
        asideText.textContent = "Aucune balade sélectionnée pour le moment.";
      } else if (checked === 1) {
        asideText.textContent = "Vous avez sélectionné 1 balade.";
      } else {
        asideText.textContent = `Vous avez sélectionné ${checked} balades.`;
      }
    }

    if (submitText && !isSubmitting) {
      submitText.textContent = checked > 0
        ? `Recevoir les programmes (${checked})`
        : "Recevoir les programmes sélectionnés";
    }

    if (submitBtn) {
      submitBtn.classList.toggle("is-active", checked > 0 && !isSubmitting);
    }
  }

  checkboxes.forEach((cb) => {
    cb.addEventListener("change", updateSelectionUI);
  });

  if (submitBtn) {
    submitBtn.addEventListener("click", function (e) {
      if (isSubmitting) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  }

  form.addEventListener("submit", function (e) {
    if (isSubmitting) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }

    isSubmitting = true;
    setSubmitLocked(true);

    // Désactive aussi les champs pour limiter les doubles interactions
    if (submitBtn) {
      submitBtn.blur();
    }

    window.setTimeout(function () {
      form.classList.add("is-submitted");
    }, 0);
  });

  updateSelectionUI();
});
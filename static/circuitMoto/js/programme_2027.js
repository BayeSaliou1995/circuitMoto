// static/circuitMoto/js/programme_2027.js
document.addEventListener("DOMContentLoaded", function () {
  const tsInput = document.querySelector('input[name="ts"]');
  if (tsInput) {
    tsInput.value = String(Math.floor(Date.now() / 1000));
  }

  const form = document.querySelector(".p27-form");
  if (!form) return;

  const cards = Array.from(form.querySelectorAll("[data-programme-card]"));
  const checkboxes = cards
    .map((card) => card.querySelector('input[type="checkbox"][name="circuits"]'))
    .filter(Boolean);

  const asideCount = document.getElementById("p27AsideCount");
  const asidePlural = document.getElementById("p27AsidePlural");
  const asideText = document.getElementById("p27AsideText");
  const liveCounter = document.getElementById("p27LiveCounter");
  const selectionCount = document.getElementById("p27SelectionCount");
  const selectionPlural = document.getElementById("p27SelectionPlural");
  const selectionHint = document.getElementById("p27SelectionHint");
  const submitBtn = document.getElementById("p27SubmitBtn");
  const submitText = document.getElementById("p27SubmitText");

  let isSubmitting = false;

  function selectedCount() {
    return checkboxes.filter((checkbox) => checkbox.checked).length;
  }

  function updateText(count) {
    const plural = count > 1 ? "s" : "";

    if (asideCount) asideCount.textContent = String(count);
    if (asidePlural) asidePlural.textContent = plural;
    if (selectionCount) selectionCount.textContent = String(count);
    if (selectionPlural) selectionPlural.textContent = plural;
    if (liveCounter) liveCounter.textContent = `${count} sélectionné${plural}`;

    if (asideText) {
      if (count === 0) {
        asideText.textContent = "Aucun circuit sélectionné pour le moment.";
      } else if (count === 1) {
        asideText.textContent = "1 circuit sélectionné. Vous pouvez préciser son niveau d'intérêt.";
      } else {
        asideText.textContent = `${count} circuits sélectionnés. Chaque circuit peut avoir son propre niveau d'intérêt.`;
      }
    }

    if (selectionHint) {
      if (count === 0) {
        selectionHint.textContent = "Cochez les voyages qui vous attirent.";
      } else if (count === 1) {
        selectionHint.textContent = "1 voyage choisi.";
      } else {
        selectionHint.textContent = `${count} voyages choisis.`;
      }
    }

    if (submitText && !isSubmitting) {
      submitText.textContent = count > 0 ? `Envoyer ma sélection (${count})` : "Envoyer ma sélection";
    }
  }

  function updateCards() {
    cards.forEach((card) => {
      const checkbox = card.querySelector('input[type="checkbox"][name="circuits"]');
      card.classList.toggle("is-selected", Boolean(checkbox && checkbox.checked));
    });

    const count = selectedCount();
    updateText(count);

    if (submitBtn) {
      submitBtn.classList.toggle("is-active", count > 0 && !isSubmitting);
    }
  }

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateCards);
  });

  form.addEventListener("submit", function (event) {
    if (isSubmitting) {
      event.preventDefault();
      event.stopPropagation();
      return false;
    }

    isSubmitting = true;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.setAttribute("aria-busy", "true");
    }
    if (submitText) {
      const count = selectedCount();
      submitText.textContent = count > 0 ? `Envoi en cours (${count})...` : "Envoi en cours...";
    }
  });

  updateCards();
});

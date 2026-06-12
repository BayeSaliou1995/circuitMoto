// static/circuitMoto/admin/css/backup-modal.js

document.addEventListener("DOMContentLoaded", function () {
  const modal = document.getElementById("backupModal");
  if (!modal) return;

  const openers = document.querySelectorAll(".js-open-backup-modal");
  const closers = modal.querySelectorAll(".js-close-backup-modal");
  const confirmBtn = document.getElementById("backupConfirmBtn");

  function openModal() {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("has-backup-modal");
    document.body.classList.add("has-backup-modal");
  }

  function closeModal() {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.documentElement.classList.remove("has-backup-modal");
    document.body.classList.remove("has-backup-modal");
  }

  openers.forEach((btn) => {
    btn.addEventListener("click", openModal);
  });

  closers.forEach((btn) => {
    btn.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  if (confirmBtn) {
    confirmBtn.addEventListener("click", function () {
      confirmBtn.disabled = true;
      confirmBtn.textContent = "Préparation du téléchargement...";
    });
  }
});
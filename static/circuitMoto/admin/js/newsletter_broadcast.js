/* =========================================================
   PAGE NEWSLETTER BROADCAST
   Fichier : static/circuitMoto/admin/js/newsletter_broadcast.js
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  const emailsField = document.getElementById("id_emails_blob");
  const validCountEl = document.getElementById("validCount");
  const invalidCountEl = document.getElementById("invalidCount");
  const fileInput = document.getElementById("id_pieces_jointes");
  const fileList = document.getElementById("filesPreview");

  /**
   * Vérifie si une chaîne ressemble à un e-mail valide.
   * Validation simple côté interface pour aperçu utilisateur.
   */
  function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Découpe le contenu collé par l’utilisateur
   * en tenant compte des espaces, virgules, retours ligne, etc.
   */
  function extractEmails(raw) {
    if (!raw) return [];

    return raw
      .split(/[\n,;\t ]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  /**
   * Compte les adresses valides et invalides
   * en supprimant les doublons.
   */
  function countEmails(raw) {
    const parts = extractEmails(raw);
    const seen = new Set();

    let valid = 0;
    let invalid = 0;

    parts.forEach((item) => {
      const normalized = item.toLowerCase();

      if (seen.has(normalized)) {
        return;
      }

      seen.add(normalized);

      if (isValidEmail(normalized)) {
        valid += 1;
      } else {
        invalid += 1;
      }
    });

    return { valid, invalid };
  }

  /**
   * Met à jour les cartes statistiques en direct.
   */
  function refreshCounts() {
    if (!emailsField) return;

    const result = countEmails(emailsField.value);

    if (validCountEl) {
      validCountEl.textContent = String(result.valid);
    }

    if (invalidCountEl) {
      invalidCountEl.textContent = String(result.invalid);
    }
  }

  /**
   * Affiche la liste des fichiers sélectionnés.
   */
  function refreshFilesPreview() {
    if (!fileInput || !fileList) return;

    fileList.innerHTML = "";

    Array.from(fileInput.files || []).forEach((file) => {
      const li = document.createElement("li");
      const sizeKo = Math.max(1, Math.round(file.size / 1024));
      li.textContent = `${file.name} (${sizeKo} Ko)`;
      fileList.appendChild(li);
    });
  }

  /* -------------------------------------------------------
     Bind événements
     ------------------------------------------------------- */
  if (emailsField) {
    emailsField.addEventListener("input", refreshCounts);
    refreshCounts();
  }

  if (fileInput) {
    fileInput.addEventListener("change", refreshFilesPreview);
  }
});
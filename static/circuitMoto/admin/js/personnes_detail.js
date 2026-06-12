// static/circuitMoto/admin/js/personnes_detail.js

(function () {
  "use strict";

  // ----------------------------
  // Helpers loading / anti double submit
  // ----------------------------
  function setLoading(btn, on) {
    if (!btn) return;
    const loadingText = btn.getAttribute("data-loading-text") || "Traitement...";

    if (on) {
      if (!btn.dataset.originalHtml) btn.dataset.originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.classList.add("is-loading");
      btn.setAttribute("aria-busy", "true");
      btn.innerHTML = loadingText;
      btn.dataset.loadingStartedAt = String(performance.now());
    } else {
      btn.disabled = false;
      btn.classList.remove("is-loading");
      btn.removeAttribute("aria-busy");
      if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
      delete btn.dataset.originalHtml;
      delete btn.dataset.loadingStartedAt;
    }
  }

  async function waitMinLoading(btn) {
    if (!btn) return;
    const minMs = parseInt(btn.getAttribute("data-loading-min-ms") || "0", 10);
    if (!minMs) return;

    const t0 = parseFloat(btn.dataset.loadingStartedAt || "0");
    if (!t0) return;

    const elapsed = performance.now() - t0;
    const remain = minMs - elapsed;
    if (remain > 0) await new Promise((r) => setTimeout(r, remain));
  }

  // ----------------------------
  // Toast
  // ----------------------------
  const ICONS = {
    success:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 6L9 17l-5-5"/></svg>',
    info:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
    warning:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
    error:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
  };

  function toastShow(message, { type = "success", duration = 2400 } = {}) {
    const wrap = document.getElementById("toast");
    if (!wrap) return;

    const card = document.createElement("div");
    card.className = "toast-card";
    card.setAttribute("data-type", type);
    card.innerHTML = `
      <span class="toast-icon" aria-hidden="true">${ICONS[type] || ICONS.info}</span>
      <div class="toast-text"></div>
      <div class="toast-progress"></div>
    `;
    card.querySelector(".toast-text").textContent = message || "";

    const bar = card.querySelector(".toast-progress");
    const t0 = performance.now();
    (function tick(now) {
      const p = Math.min(1, (now - t0) / duration);
      bar.style.transform = `scaleX(${1 - p})`;
      if (p < 1) card._raf = requestAnimationFrame(tick);
    })(t0);

    card._to = setTimeout(() => {
      card.style.animation = "toast-out .15s ease forwards";
      setTimeout(() => card.remove(), 160);
    }, Math.max(800, duration));

    wrap.appendChild(card);
  }

  // ----------------------------
  // Modal
  // ----------------------------
  const overlay = document.getElementById("modal-overlay");
  const modal = overlay?.querySelector(".modal");
  const btnOk = document.getElementById("modal-confirm");
  const btnKo = document.getElementById("modal-cancel");
  const btnX = document.getElementById("modal-close");
  const titleEl = document.getElementById("modal-title");
  const msgEl = document.getElementById("modal-message");
  const inputWrap = overlay?.querySelector(".modal-input");
  const inputEl = document.getElementById("modal-input");

  const FOCUS = 'a,button,input,select,textarea,[tabindex]:not([tabindex="-1"])';

  function installModalEvents() {
    if (!overlay || !modal) return;

    const focusables = Array.from(modal.querySelectorAll(FOCUS)).filter(
      (el) => !el.disabled && el.offsetParent !== null
    );

    function onKey(e) {
      if (e.key === "Escape") modalClose();

      if (e.key === "Tab" && focusables.length) {
        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    function onOverlay(e) {
      if (e.target === overlay) modalClose();
    }

    overlay._cleanup = () => {
      document.removeEventListener("keydown", onKey);
      overlay.removeEventListener("mousedown", onOverlay);
    };

    document.addEventListener("keydown", onKey);
    overlay.addEventListener("mousedown", onOverlay);
  }

  function modalOpen({
    title = "Confirmer l’action",
    message = "Êtes-vous sûr ?",
    withInput = false,
    placeholder = "",
  }) {
    if (!overlay || !modal || !titleEl || !msgEl || !inputWrap) return;

    titleEl.textContent = title;
    msgEl.textContent = message;

    inputWrap.classList.toggle("hidden", !withInput);
    if (withInput && inputEl) {
      inputEl.value = "";
      inputEl.placeholder = placeholder || "";
    }

    overlay.classList.add("active");
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");

    installModalEvents();

    const focusables = Array.from(modal.querySelectorAll(FOCUS)).filter(
      (el) => !el.disabled && el.offsetParent !== null
    );
    (withInput ? inputEl : focusables[0])?.focus();
  }

  function modalOpenHtml({
    title = "Aperçu",
    html = "",
    confirmText = "Confirmer",
    cancelText = "Annuler",
    confirmClass = "btn btn-primary",
  }) {
    if (!overlay || !modal || !titleEl || !msgEl || !inputWrap || !btnOk || !btnKo) return;

    titleEl.textContent = title;
    msgEl.innerHTML = html;
    inputWrap.classList.add("hidden");

    btnOk.textContent = confirmText;
    btnKo.textContent = cancelText;
    btnOk.className = confirmClass;

    overlay.classList.add("active");
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");

    installModalEvents();

    const firstFocusable = modal.querySelector(FOCUS);
    firstFocusable?.focus();
  }

  function modalClose() {
    if (!overlay || !msgEl) return;
    overlay.classList.remove("active");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    msgEl.innerHTML = "";
    overlay._cleanup?.();
  }

  function modalConfirm(message) {
    return new Promise((resolve) => {
      modalOpen({ message });

      const ok = () => cleanup(true);
      const ko = () => cleanup(false);

      function cleanup(v) {
        btnOk?.removeEventListener("click", ok);
        btnKo?.removeEventListener("click", ko);
        btnX?.removeEventListener("click", ko);
        modalClose();
        resolve(v);
      }

      btnOk?.addEventListener("click", ok);
      btnKo?.addEventListener("click", ko);
      btnX?.addEventListener("click", ko);
    });
  }

  function modalPrompt(message, placeholder = "") {
    return new Promise((resolve) => {
      modalOpen({ message, withInput: true, placeholder });

      const ok = () => cleanup(inputEl?.value.trim() || null);
      const ko = () => cleanup(null);

      function onKey(e) {
        if (e.key === "Enter") ok();
      }

      function cleanup(v) {
        btnOk?.removeEventListener("click", ok);
        btnKo?.removeEventListener("click", ko);
        btnX?.removeEventListener("click", ko);
        inputEl?.removeEventListener("keydown", onKey);
        modalClose();
        resolve(v);
      }

      btnOk?.addEventListener("click", ok);
      btnKo?.addEventListener("click", ko);
      btnX?.addEventListener("click", ko);
      inputEl?.addEventListener("keydown", onKey);
      setTimeout(() => inputEl?.focus(), 40);
    });
  }

  function modalConfirmHtml({
    title = "Confirmer",
    html = "",
    confirmText = "Confirmer",
    cancelText = "Annuler",
    confirmClass = "btn btn-primary",
  }) {
    return new Promise((resolve) => {
      if (!overlay || !titleEl || !msgEl || !btnOk || !btnKo || !inputWrap) {
        resolve(false);
        return;
      }

      const prevTitle = titleEl.innerHTML;
      const prevHtml = msgEl.innerHTML;
      const prevOkText = btnOk.textContent;
      const prevKoText = btnKo.textContent;
      const prevOkClass = btnOk.className;
      const prevOkOnClick = btnOk.onclick;
      const prevKoOnClick = btnKo.onclick;
      const prevXOnClick = btnX ? btnX.onclick : null;

      titleEl.textContent = title;
      msgEl.innerHTML = html;
      inputWrap.classList.add("hidden");

      btnOk.textContent = confirmText;
      btnKo.textContent = cancelText;
      btnOk.className = confirmClass;

      const ok = () => cleanup(true);
      const ko = () => cleanup(false);

      function cleanup(value) {
        btnOk.removeEventListener("click", ok);
        btnKo.removeEventListener("click", ko);
        btnX?.removeEventListener("click", ko);

        titleEl.innerHTML = prevTitle;
        msgEl.innerHTML = prevHtml;
        btnOk.textContent = prevOkText;
        btnKo.textContent = prevKoText;
        btnOk.className = prevOkClass;
        btnOk.onclick = prevOkOnClick;
        btnKo.onclick = prevKoOnClick;
        if (btnX) btnX.onclick = prevXOnClick;

        resolve(value);
      }

      btnOk.onclick = null;
      btnKo.onclick = null;
      if (btnX) btnX.onclick = null;

      btnOk.addEventListener("click", ok);
      btnKo.addEventListener("click", ko);
      btnX?.addEventListener("click", ko);
    });
  }

  // ----------------------------
  // Tabs init
  // ----------------------------
  function initTabs() {
    const personDetailRoot = document.querySelector(".person-detail-container");
    const personName = document.querySelector(".person-name")?.textContent?.trim() || "";
    const pageKeyBase = `personne-detail:${window.location.pathname}:${personName}`;

    const MAIN_TAB_KEY = `${pageKeyBase}:main-tab`;
    const INS_TAB_KEY = `${pageKeyBase}:ins-tab`;

    const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
    const tabContents = Array.from(document.querySelectorAll(".tab-content"));

    const insTabButtons = Array.from(document.querySelectorAll(".ins-tab-btn"));
    const insTabContents = Array.from(document.querySelectorAll(".ins-tab-content"));

    function activateMainTab(tabName, { save = true } = {}) {
      if (!tabName) return;

      const target = document.getElementById(`${tabName}-tab`);
      const btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
      if (!target || !btn) return;

      tabButtons.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      target.classList.add("active");

      if (save) {
        localStorage.setItem(MAIN_TAB_KEY, tabName);
      }
    }

    function activateInsTab(tabName, { save = true } = {}) {
      if (!tabName) return;

      const target = document.getElementById(`${tabName}-tab`);
      const btn = document.querySelector(`.ins-tab-btn[data-ins-tab="${tabName}"]`);
      if (!target || !btn) return;

      insTabButtons.forEach((b) => b.classList.remove("active"));
      insTabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      target.classList.add("active");

      if (save) {
        localStorage.setItem(INS_TAB_KEY, tabName);
      }
    }

    tabButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tabName = btn.getAttribute("data-tab");
        activateMainTab(tabName);
      });
    });

    insTabButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tabName = btn.getAttribute("data-ins-tab");
        activateInsTab(tabName);
      });
    });

    const savedMainTab = localStorage.getItem(MAIN_TAB_KEY);
    const savedInsTab = localStorage.getItem(INS_TAB_KEY);

    if (savedMainTab && document.getElementById(`${savedMainTab}-tab`)) {
      activateMainTab(savedMainTab, { save: false });
    } else if (tabButtons.length) {
      const defaultMain =
        document.querySelector(".tab-btn.active")?.getAttribute("data-tab") ||
        tabButtons[0].getAttribute("data-tab");
      activateMainTab(defaultMain, { save: false });
    }

    if (insTabButtons.length) {
      if (savedInsTab && document.getElementById(`${savedInsTab}-tab`)) {
        activateInsTab(savedInsTab, { save: false });
      } else {
        const defaultIns =
          document.querySelector(".ins-tab-btn.active")?.getAttribute("data-ins-tab") ||
          insTabButtons[0].getAttribute("data-ins-tab");
        activateInsTab(defaultIns, { save: false });
      }
    }
  }

  // ----------------------------
  // AJAX helpers
  // ----------------------------
  async function postAjaxForm(form, submitter, extra = {}) {
    const fd = new FormData(form);
    if (submitter && submitter.name) fd.append(submitter.name, submitter.value);
    Object.entries(extra).forEach(([k, v]) => fd.set(k, v));

    const url = form.getAttribute("action") || window.location.href;
    const res = await fetch(url, {
      method: "POST",
      body: fd,
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      const err = new Error(data.message || `Erreur HTTP ${res.status}`);
      err.payload = data;
      throw err;
    }
    return data;
  }

  function updateTelUrgence(payload) {
    const wrap = document.querySelector(
      `[data-ins-id="${payload.ins_id}"] [data-col="tel-urgence"]`
    );
    if (wrap) wrap.textContent = payload.telephone_urgence || "—";
  }

  function updateInscriptionUI(payload) {
    const card = document.querySelector(`[data-ins-id="${payload.id}"]`);
    if (!card) return;

    const statutChip = card.querySelector('[data-col="ins-statut"]');
    if (statutChip) {
      statutChip.textContent = payload.statut_label || payload.statut || "—";
    }

    const actions =
      card.querySelector('[data-col="ins-actions"]') ||
      card.querySelector(".ins-actions");

    if (actions) {
      const validateForm = actions
        .querySelector('form.js-ajax-form button[name="action"][value="ins_validate"]')
        ?.closest("form");

      if (validateForm) validateForm.remove();
    }
  }

  function ensureOptionsAddedBox(summaryBox) {
    let box = summaryBox.querySelector('[data-col="options-added-box"]');
    if (box) return box;

    box = document.createElement("div");
    box.className = "payment-summary-item warning";
    box.setAttribute("data-col", "options-added-box");
    box.innerHTML = `
      <span class="label">Options ajoutées</span>
      <strong data-col="options-added-value">0</strong>
    `;

    const statusBox = summaryBox.querySelector('[data-col="payment-status-box"]');
    if (statusBox && statusBox.parentNode === summaryBox) {
      summaryBox.insertBefore(box, statusBox);
    } else {
      summaryBox.appendChild(box);
    }

    return box;
  }

  function updatePaymentTable(payments, summary) {
    if (!Array.isArray(payments) || !summary) return;

    const card = document.querySelector(`[data-ins-id="${summary.ins_id}"]`);
    if (!card) return;

    payments.forEach((payment) => {
      const row = card.querySelector(`tr[data-payment-id="${payment.id}"]`);
      if (!row) return;

      const montantCell = row.querySelector('[data-col="montant-encaisse"]');
      const dateCell = row.querySelector('[data-col="encaisse-le"]');
      const statutCell = row.querySelector('[data-col="statut"]');

      if (montantCell) {
        montantCell.textContent = `${payment.montant_encaisse} ${summary.devise}`;
      }

      if (dateCell) {
        dateCell.textContent = payment.encaisse_le || "—";
      }

      if (statutCell) {
        statutCell.textContent = payment.statut_label || payment.statut || "—";
      }
    });

    const summaryBox = card.querySelector(`[data-payment-summary="${summary.ins_id}"]`);
    if (!summaryBox) return;

    const totalPayeEl = summaryBox.querySelector('[data-col="total-paye"]');
    const totalAttenduEl = summaryBox.querySelector('[data-col="total-attendu"]');
    const statusBox = summaryBox.querySelector('[data-col="payment-status-box"]');

    if (totalPayeEl) {
      totalPayeEl.textContent = `${summary.total_paye} ${summary.devise}`;
    }

    if (totalAttenduEl) {
      totalAttenduEl.textContent = `${summary.total_attendu} ${summary.devise}`;
    }

    const optionsAdded = Number(String(summary.options_added || "0").replace(",", "."));
    let optionsBox = summaryBox.querySelector('[data-col="options-added-box"]');

    if (optionsAdded > 0) {
      optionsBox = ensureOptionsAddedBox(summaryBox);
      const optionsValue = optionsBox.querySelector('[data-col="options-added-value"]');
      if (optionsValue) {
        optionsValue.textContent = `${summary.options_added} ${summary.devise}`;
      }
      optionsBox.hidden = false;
    } else if (optionsBox) {
      optionsBox.hidden = true;
    }

    if (statusBox) {
      if (summary.payment_state === "reste") {
        statusBox.className = "payment-summary-item highlight warning";
        statusBox.innerHTML = `
          <span class="label">Reste à payer</span>
          <strong data-col="reste-a-payer">${summary.reste_a_payer} ${summary.devise}</strong>
        `;
      } else if (summary.payment_state === "trop_percu") {
        statusBox.className = "payment-summary-item highlight success";
        statusBox.innerHTML = `
          <span class="label">Trop-perçu</span>
          <strong data-col="trop-percu">${summary.trop_percu} ${summary.devise}</strong>
        `;
      } else {
        statusBox.className = "payment-summary-item highlight success";
        statusBox.innerHTML = `
          <span class="label">Situation</span>
          <strong data-col="payment-state-label">Soldé</strong>
        `;
      }
    }
  }

  // ----------------------------
  // Payment summary modal flow
  // ----------------------------
  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getDecimalValue(form, name) {
    const value = form.querySelector(`[name="${name}"]`)?.value || "0";
    const normalized = String(value).replace(",", ".");
    const n = parseFloat(normalized);
    return isNaN(n) ? 0 : n;
  }

  function formatMoney(value) {
    const n = Number(value || 0);
    return new Intl.NumberFormat("fr-FR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  }

  function formatDateFr(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return new Intl.DateTimeFormat("fr-FR").format(d);
  }

  function computePaymentTotals(form) {
    const totalAttenduInitial = getDecimalValue(form, "total_attendu");
    const montantOptionsAjoutees = getDecimalValue(form, "montant_options_ajoutees");
    const nouveauTotalAttendu = totalAttenduInitial + montantOptionsAjoutees;

    const acompte1 = getDecimalValue(form, "acompte1_encaisse");
    const acompte2 = getDecimalValue(form, "acompte2_encaisse");
    const solde = getDecimalValue(form, "solde_encaisse");
    const paiementOptions = getDecimalValue(form, "paiement_recu_pour_options");

    const totalSaisi = acompte1 + acompte2 + solde + paiementOptions;

    let restant = 0;
    let trop = 0;
    let situation = "Soldé";

    if (totalSaisi < nouveauTotalAttendu) {
      restant = nouveauTotalAttendu - totalSaisi;
      situation = "Reste à payer";
    } else if (totalSaisi > nouveauTotalAttendu) {
      trop = totalSaisi - nouveauTotalAttendu;
      situation = "Trop-perçu";
    }

    return {
      totalAttenduInitial,
      montantOptionsAjoutees,
      nouveauTotalAttendu,
      acompte1,
      acompte2,
      solde,
      paiementOptions,
      totalSaisi,
      restant,
      trop,
      situation,
    };
  }

  function autoComputePaymentFields(form) {
    const {
      nouveauTotalAttendu,
      restant,
      trop,
      situation,
      montantOptionsAjoutees,
      paiementOptions,
    } = computePaymentTotals(form);

    const nouveauTotalInput = form.querySelector('[name="nouveau_total_attendu"]');
    const restantInput = form.querySelector('[name="montant_restant"]');
    const tropPercuInput = form.querySelector('[name="trop_percu"]');
    const situationInput = form.querySelector('[name="situation_label"]');

    if (nouveauTotalInput) nouveauTotalInput.value = nouveauTotalAttendu.toFixed(2);
    if (restantInput) restantInput.value = restant.toFixed(2);
    if (tropPercuInput) tropPercuInput.value = trop.toFixed(2);

    if (situationInput && !situationInput.dataset.userEdited) {
      if (montantOptionsAjoutees > 0 && paiementOptions > 0) {
        situationInput.value = "Paiement reçu après ajout d’options";
      } else {
        situationInput.value = situation;
      }
    }
  }

  function toggleOptionsAddedBlocks(form) {
    const montantOptions = getDecimalValue(form, "montant_options_ajoutees");
    const blocks = form.querySelectorAll("[data-options-added-block]");
    const show = montantOptions > 0;

    blocks.forEach((el) => {
      el.hidden = !show;
    });
  }

  function buildPaymentPreview(form) {
    const sujet = form.querySelector('[name="sujet"]')?.value || "";
    const intro = form.querySelector('[name="intro_message"]')?.value || "";
    const note = form.querySelector('[name="note_client"]')?.value || "";
    const infos = form.querySelector('[name="infos_paiement_custom"]')?.value || "";
    const situation = form.querySelector('[name="situation_label"]')?.value || "";
    const datePaiement = form.querySelector('[name="date_paiement"]')?.value || "";

    const {
      totalAttenduInitial,
      montantOptionsAjoutees,
      nouveauTotalAttendu,
      acompte1,
      acompte2,
      solde,
      paiementOptions,
      totalSaisi,
      restant,
      trop,
    } = computePaymentTotals(form);

    const includeDetails = form.querySelector('[name="inclure_detail_paiements"]')?.checked;
    const includeInfos = form.querySelector('[name="inclure_infos_paiement"]')?.checked;
    const preview = form.querySelector("#paysum-live-preview");

    if (!preview) return;

    const detailsHint = includeDetails
      ? `<div class="mail-preview-note">Le détail des paiements enregistrés sera inclus dans l’e-mail.</div>`
      : `<div class="mail-preview-note">Le détail des paiements enregistrés ne sera pas inclus.</div>`;

    const infosBlock = includeInfos && infos
      ? `
        <div class="mail-preview-section">
          <div class="mail-preview-label">Informations de paiement</div>
          <div class="mail-preview-text">${escapeHtml(infos).replace(/\n/g, "<br>")}</div>
        </div>
      `
      : "";

    const noteBlock = note
      ? `
        <div class="mail-preview-section">
          <div class="mail-preview-label">Message complémentaire</div>
          <div class="mail-preview-text">${escapeHtml(note).replace(/\n/g, "<br>")}</div>
        </div>
      `
      : "";

    const dateBlock = datePaiement
      ? `
        <div class="mail-preview-section">
          <div class="mail-preview-label">Date du paiement</div>
          <div class="mail-preview-text"><strong>${escapeHtml(formatDateFr(datePaiement))}</strong></div>
        </div>
      `
      : "";

    const optionsAddedStats = montantOptionsAjoutees > 0
      ? `
        <div class="mail-preview-stat">
          <span>Options ajoutées</span>
          <strong>${formatMoney(montantOptionsAjoutees)}</strong>
        </div>
        <div class="mail-preview-stat">
          <span>Nouveau total</span>
          <strong>${formatMoney(nouveauTotalAttendu)}</strong>
        </div>
        <div class="mail-preview-stat">
          <span>Paiement options</span>
          <strong>${formatMoney(paiementOptions)}</strong>
        </div>
      `
      : "";

    preview.innerHTML = `
      <div class="mail-preview-card">
        <div class="mail-preview-subject"><strong>Sujet :</strong> ${escapeHtml(sujet)}</div>

        <div class="mail-preview-section">
          <div class="mail-preview-label">Introduction</div>
          <div class="mail-preview-text">${escapeHtml(intro).replace(/\n/g, "<br>") || "<em>Aucune introduction</em>"}</div>
        </div>

        ${dateBlock}

        <div class="mail-preview-grid">
          <div class="mail-preview-stat">
            <span>Total initial</span>
            <strong>${formatMoney(totalAttenduInitial)}</strong>
          </div>

          ${optionsAddedStats}

          <div class="mail-preview-stat">
            <span>Acompte 1</span>
            <strong>${formatMoney(acompte1)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Acompte 2</span>
            <strong>${formatMoney(acompte2)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Solde</span>
            <strong>${formatMoney(solde)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Total saisi</span>
            <strong>${formatMoney(totalSaisi)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Reste à payer</span>
            <strong>${formatMoney(restant)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Trop-perçu</span>
            <strong>${formatMoney(trop)}</strong>
          </div>
        </div>

        <div class="mail-preview-section">
          <div class="mail-preview-label">Situation</div>
          <div class="mail-preview-badge">${escapeHtml(situation || "—")}</div>
        </div>

        ${noteBlock}
        ${infosBlock}
        ${detailsHint}
      </div>
    `;
  }

  function bindPaymentSummaryModal() {
    const form = msgEl?.querySelector(".js-payment-summary-form");
    if (!form || !btnOk || !btnKo) return;

    const situationInput = form.querySelector('[name="situation_label"]');
    if (situationInput) {
      situationInput.addEventListener("input", function () {
        this.dataset.userEdited = "1";
      });
    }

    const recalcInputs = [
      form.querySelector('[name="total_attendu"]'),
      form.querySelector('[name="montant_options_ajoutees"]'),
      form.querySelector('[name="nouveau_total_attendu"]'),
      form.querySelector('[name="acompte1_encaisse"]'),
      form.querySelector('[name="acompte2_encaisse"]'),
      form.querySelector('[name="solde_encaisse"]'),
      form.querySelector('[name="paiement_recu_pour_options"]'),
      form.querySelector('[name="date_paiement"]'),
    ].filter(Boolean);

    recalcInputs.forEach((input) => {
      const evtName = input.type === "date" || input.tagName === "SELECT" ? "change" : "input";
      input.addEventListener(evtName, () => {
        autoComputePaymentFields(form);
        toggleOptionsAddedBlocks(form);
        buildPaymentPreview(form);
      });
      input.addEventListener("change", () => {
        autoComputePaymentFields(form);
        toggleOptionsAddedBlocks(form);
        buildPaymentPreview(form);
      });
    });

    form.addEventListener("input", () => buildPaymentPreview(form));
    form.addEventListener("change", () => buildPaymentPreview(form));

    autoComputePaymentFields(form);
    toggleOptionsAddedBlocks(form);
    buildPaymentPreview(form);

    const sendHandler = async () => {
      const sujetInput = form.querySelector('[name="sujet"]');
      const liveSituationInput = form.querySelector('[name="situation_label"]');
      const recipientSelect = form.querySelector('[name="recipient_role"]');
      const includeDetails = form.querySelector('[name="inclure_detail_paiements"]');
      const includeInfos = form.querySelector('[name="inclure_infos_paiement"]');
      const datePaiementInput = form.querySelector('[name="date_paiement"]');

      const acompte1Input = form.querySelector('[name="acompte1_encaisse"]');
      const acompte2Input = form.querySelector('[name="acompte2_encaisse"]');
      const soldeInput = form.querySelector('[name="solde_encaisse"]');
      const paiementOptionsInput = form.querySelector('[name="paiement_recu_pour_options"]');

      const acompte1 = getDecimalValue(form, "acompte1_encaisse");
      const acompte2 = getDecimalValue(form, "acompte2_encaisse");
      const solde = getDecimalValue(form, "solde_encaisse");
      const paiementOptions = getDecimalValue(form, "paiement_recu_pour_options");
      const totalSaisi = acompte1 + acompte2 + solde + paiementOptions;

      if (totalSaisi <= 0) {
        toastShow("Merci de saisir au moins un montant encaissé.", {
          type: "warning",
          duration: 3500,
        });
        (acompte1Input || acompte2Input || soldeInput || paiementOptionsInput)?.focus();
        return;
      }

      if (!datePaiementInput?.value) {
        toastShow("Merci de renseigner la date du paiement avant l’envoi.", {
          type: "warning",
          duration: 3500,
        });
        datePaiementInput?.focus();
        return;
      }

      autoComputePaymentFields(form);
      toggleOptionsAddedBlocks(form);
      buildPaymentPreview(form);

      const sujet = sujetInput?.value || "Récapitulatif de paiement";
      const destinataire = recipientSelect?.selectedOptions?.[0]?.textContent || "Destinataire";
      const {
        totalAttenduInitial,
        montantOptionsAjoutees,
        nouveauTotalAttendu,
        restant,
        trop,
      } = computePaymentTotals(form);

      const situation = liveSituationInput?.value || "—";
      const datePaiement = datePaiementInput.value;

      const optionsConfirmStats = montantOptionsAjoutees > 0
        ? `
          <div class="mail-confirm-stat">
            <span>Options ajoutées</span>
            <strong>${formatMoney(montantOptionsAjoutees)}</strong>
          </div>
          <div class="mail-confirm-stat">
            <span>Nouveau total</span>
            <strong>${formatMoney(nouveauTotalAttendu)}</strong>
          </div>
          <div class="mail-confirm-stat">
            <span>Paiement options</span>
            <strong>${formatMoney(paiementOptions)}</strong>
          </div>
        `
        : "";

      const confirmHtml = `
        <div class="mail-confirm-card">
          <div class="mail-confirm-row">
            <span>Destinataire</span>
            <strong>${escapeHtml(destinataire)}</strong>
          </div>

          <div class="mail-confirm-row">
            <span>Sujet</span>
            <strong>${escapeHtml(sujet)}</strong>
          </div>

          <div class="mail-confirm-row">
            <span>Date du paiement</span>
            <strong>${escapeHtml(formatDateFr(datePaiement))}</strong>
          </div>

          <div class="mail-confirm-grid">
            <div class="mail-confirm-stat">
              <span>Total initial</span>
              <strong>${formatMoney(totalAttenduInitial)}</strong>
            </div>

            ${optionsConfirmStats}

            <div class="mail-confirm-stat">
              <span>Acompte 1 saisi</span>
              <strong>${formatMoney(acompte1)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Acompte 2 saisi</span>
              <strong>${formatMoney(acompte2)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Solde saisi</span>
              <strong>${formatMoney(solde)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Total saisi</span>
              <strong>${formatMoney(totalSaisi)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Reste à payer</span>
              <strong>${formatMoney(restant)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Trop-perçu</span>
              <strong>${formatMoney(trop)}</strong>
            </div>
          </div>

          <div class="mail-confirm-row">
            <span>Situation</span>
            <strong>${escapeHtml(situation)}</strong>
          </div>

          <div class="mail-confirm-flags">
            <div>• Détail des paiements : <strong>${includeDetails?.checked ? "Oui" : "Non"}</strong></div>
            <div>• Informations de paiement : <strong>${includeInfos?.checked ? "Oui" : "Non"}</strong></div>
          </div>

          <div class="mail-confirm-warning">
            Merci de vérifier attentivement ces informations avant l’envoi. Les montants saisis seront appliqués dynamiquement sur les échéances en tenant compte des arriérés.
          </div>
        </div>
      `;

      const confirmed = await modalConfirmHtml({
        title: "Confirmer l’envoi du récapitulatif",
        html: confirmHtml,
        confirmText: "Confirmer et envoyer",
        cancelText: "Retour",
        confirmClass: "btn btn-primary",
      });

      if (!confirmed) {
        bindPaymentSummaryModal();
        return;
      }

      if (form.dataset.submitting === "1") return;
      form.dataset.submitting = "1";
      setLoading(btnOk, true);

      try {
        const data = await postAjaxForm(form, null);

        if (data.payments && data.payment_summary) {
          updatePaymentTable(data.payments, data.payment_summary);
        }

        toastShow(data.message || "Récapitulatif envoyé.", { type: "success" });
        modalClose();
      } catch (err) {
        if (err.payload && err.payload.modal_html && msgEl) {
          msgEl.innerHTML = err.payload.modal_html;
          bindPaymentSummaryModal();
          toastShow(err.message || "Merci de corriger le formulaire.", {
            type: "warning",
            duration: 3500,
          });
          return;
        }

        toastShow(err.message || "Erreur lors de l’envoi.", {
          type: "error",
          duration: 4000,
        });
      } finally {
        await waitMinLoading(btnOk);
        setLoading(btnOk, false);
        form.dataset.submitting = "0";
      }
    };

    btnOk.textContent = "Envoyer";
    btnOk.className = "btn btn-primary";
    btnOk.onclick = sendHandler;

    btnKo.onclick = modalClose;
    if (btnX) btnX.onclick = modalClose;
  }

  async function openPaymentSummaryComposer(form, submitter) {
    if (form.dataset.submitting === "1") return;
    form.dataset.submitting = "1";
    setLoading(submitter, true);

    try {
      const data = await postAjaxForm(form, null);
      modalOpenHtml({
        title: "Préparer le récapitulatif de paiement",
        html: data.modal_html || "",
        confirmText: "Envoyer",
        cancelText: "Annuler",
        confirmClass: "btn btn-primary",
      });
      bindPaymentSummaryModal();
    } catch (err) {
      toastShow(err.message || "Impossible de préparer le récapitulatif.", {
        type: "error",
        duration: 4000,
      });
    } finally {
      await waitMinLoading(submitter);
      setLoading(submitter, false);
      form.dataset.submitting = "0";
    }
  }

  // ----------------------------
  // Generic AJAX forms
  // ----------------------------
  document.addEventListener(
    "submit",
    async (e) => {
      const payForm = e.target.closest("form.js-payment-summary-open");
      if (payForm) {
        e.preventDefault();
        const submitter = e.submitter || payForm.querySelector('button[type="submit"]');
        await openPaymentSummaryComposer(payForm, submitter);
        return;
      }


      const reminderForm = e.target.closest("form.js-payment-reminder-open");
      if (reminderForm) {
        e.preventDefault();
        const submitter = e.submitter || reminderForm.querySelector('button[type="submit"]');
        await openPaymentReminderComposer(reminderForm, submitter);
        return;
      }

      const form = e.target.closest("form.js-ajax-form");
      if (!form) return;

      e.preventDefault();

      if (form.dataset.submitting === "1") return;
      form.dataset.submitting = "1";

      const submitter = e.submitter || document.activeElement;
      const isOnce = submitter?.classList?.contains("js-once");
      if (isOnce) setLoading(submitter, true);

      try {
        const val = submitter?.value;
        let extra = {};

        if (val === "doc_reset") {
          const ok = await modalConfirm("Réinitialiser ce document en « En attente » ?");
          if (!ok) return;
        }

        if (val === "doc_refuse") {
          const raison = await modalPrompt(
            "Motif du refus",
            "Document flou / nom illisible / périmé…"
          );
          if (!raison) return;
          extra = { raison };
        }

        const data = await postAjaxForm(form, submitter, extra);

        if (data.ins) updateInscriptionUI(data.ins);
        if (data.assurance) updateTelUrgence(data.assurance);

        toastShow(data.message || "Action effectuée", { type: "success" });

        if (data.hide_submitter === true && submitter) {
          submitter.style.display = "none";
        }
      } catch (err) {
        toastShow(err.message || "Erreur", {
          type: "error",
          duration: 4000,
        });
      } finally {
        await waitMinLoading(submitter);
        form.dataset.submitting = "0";
        if (isOnce) setLoading(submitter, false);
      }
    },
    true
  );

  function buildPaymentReminderPreview(form) {
    const sujet = form.querySelector('[name="sujet"]')?.value || "";
    const intro = form.querySelector('[name="intro_message"]')?.value || "";
    const note = form.querySelector('[name="note_client"]')?.value || "";
    const infos = form.querySelector('[name="infos_paiement_custom"]')?.value || "";
    const totalAttendu = getDecimalValue(form, "total_attendu");
    const totalPaye = getDecimalValue(form, "total_paye");
    const restant = getDecimalValue(form, "montant_restant");
    const situation = form.querySelector('[name="situation_label"]')?.value || "Reste à payer";
    const includeDetails = form.querySelector('[name="inclure_detail_paiements"]')?.checked;
    const includeInfos = form.querySelector('[name="inclure_infos_paiement"]')?.checked;

    const preview = form.querySelector("#payrem-live-preview");
    if (!preview) return;

    const infosBlock = includeInfos && infos
      ? `
        <div class="mail-preview-section">
          <div class="mail-preview-label">Informations de paiement</div>
          <div class="mail-preview-text">${escapeHtml(infos).replace(/\n/g, "<br>")}</div>
        </div>
      `
      : "";

    const noteBlock = note
      ? `
        <div class="mail-preview-section">
          <div class="mail-preview-label">Message complémentaire</div>
          <div class="mail-preview-text">${escapeHtml(note).replace(/\n/g, "<br>")}</div>
        </div>
      `
      : "";

    preview.innerHTML = `
      <div class="mail-preview-card">
        <div class="mail-preview-subject"><strong>Sujet :</strong> ${escapeHtml(sujet)}</div>

        <div class="mail-preview-section">
          <div class="mail-preview-label">Introduction</div>
          <div class="mail-preview-text">${escapeHtml(intro).replace(/\n/g, "<br>") || "<em>Aucune introduction</em>"}</div>
        </div>

        <div class="mail-preview-grid">
          <div class="mail-preview-stat">
            <span>Total attendu</span>
            <strong>${formatMoney(totalAttendu)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Déjà payé</span>
            <strong>${formatMoney(totalPaye)}</strong>
          </div>
          <div class="mail-preview-stat">
            <span>Reste à payer</span>
            <strong>${formatMoney(restant)}</strong>
          </div>
        </div>

        <div class="mail-preview-section">
          <div class="mail-preview-label">État du paiement</div>
          <div class="mail-preview-badge">${escapeHtml(situation)}</div>
        </div>

        ${noteBlock}
        ${infosBlock}

        <div class="mail-preview-note">
          ${includeDetails ? "Le détail des paiements enregistrés sera inclus dans l’e-mail." : "Le détail des paiements enregistrés ne sera pas inclus."}
        </div>
      </div>
    `;
  }

  function bindPaymentReminderModal() {
    const form = msgEl?.querySelector(".js-payment-reminder-form");
    if (!form || !btnOk || !btnKo) return;

    if (!form.dataset.previewBound) {
      form.addEventListener("input", () => buildPaymentReminderPreview(form));
      form.addEventListener("change", () => buildPaymentReminderPreview(form));
      form.dataset.previewBound = "1";
    }
    buildPaymentReminderPreview(form);

    const sendHandler = async () => {
      const sujet = form.querySelector('[name="sujet"]')?.value || "Rappel de paiement";
      const destinataire = form.querySelector('[name="recipient_role"]')?.selectedOptions?.[0]?.textContent || "Destinataire";
      const restant = getDecimalValue(form, "montant_restant");
      const totalAttendu = getDecimalValue(form, "total_attendu");
      const totalPaye = getDecimalValue(form, "total_paye");
      const situation = form.querySelector('[name="situation_label"]')?.value || "Reste à payer";

      if (restant <= 0) {
        toastShow("Le paiement est déjà soldé. Aucun rappel à envoyer.", {
          type: "warning",
          duration: 3500,
        });
        return;
      }

      const confirmHtml = `
        <div class="mail-confirm-card">
          <div class="mail-confirm-row">
            <span>Destinataire</span>
            <strong>${escapeHtml(destinataire)}</strong>
          </div>
          <div class="mail-confirm-row">
            <span>Sujet</span>
            <strong>${escapeHtml(sujet)}</strong>
          </div>

          <div class="mail-confirm-grid">
            <div class="mail-confirm-stat">
              <span>Total attendu</span>
              <strong>${formatMoney(totalAttendu)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Déjà payé</span>
              <strong>${formatMoney(totalPaye)}</strong>
            </div>
            <div class="mail-confirm-stat">
              <span>Reste à payer</span>
              <strong>${formatMoney(restant)}</strong>
            </div>
          </div>

          <div class="mail-confirm-row">
            <span>Situation</span>
            <strong>${escapeHtml(situation)}</strong>
          </div>

          <div class="mail-confirm-warning">
            Ce rappel sera envoyé au client avec l’état actuel de son paiement non soldé.
          </div>
        </div>
      `;

      const confirmed = await modalConfirmHtml({
        title: "Confirmer l’envoi du rappel",
        html: confirmHtml,
        confirmText: "Confirmer et envoyer",
        cancelText: "Retour",
        confirmClass: "btn btn-warning",
      });

      if (!confirmed) {
        bindPaymentReminderModal();
        return;
      }

      if (form.dataset.submitting === "1") return;
      form.dataset.submitting = "1";
      setLoading(btnOk, true);

      try {
        const data = await postAjaxForm(form, null);

        if (data.payment_summary) {
          updatePaymentTable([], data.payment_summary);
        }

        toastShow(data.message || "Rappel envoyé.", { type: "success" });
        modalClose();
      } catch (err) {
        if (err.payload && err.payload.modal_html && msgEl) {
          msgEl.innerHTML = err.payload.modal_html;
          bindPaymentReminderModal();
          toastShow(err.message || "Merci de corriger le formulaire.", {
            type: "warning",
            duration: 3500,
          });
          return;
        }

        toastShow(err.message || "Erreur lors de l’envoi du rappel.", {
          type: "error",
          duration: 4000,
        });
      } finally {
        await waitMinLoading(btnOk);
        setLoading(btnOk, false);
        form.dataset.submitting = "0";
      }
    };

    btnOk.textContent = "Envoyer";
    btnOk.className = "btn btn-warning";
    btnOk.onclick = sendHandler;

    btnKo.onclick = modalClose;
    if (btnX) btnX.onclick = modalClose;
  }

  async function openPaymentReminderComposer(form, submitter) {
    if (form.dataset.submitting === "1") return;
    form.dataset.submitting = "1";
    setLoading(submitter, true);

    try {
      const data = await postAjaxForm(form, null);
      modalOpenHtml({
        title: "Préparer le rappel de paiement",
        html: data.modal_html || "",
        confirmText: "Envoyer",
        cancelText: "Annuler",
        confirmClass: "btn btn-warning",
      });
      bindPaymentReminderModal();
    } catch (err) {
      toastShow(err.message || "Impossible de préparer le rappel.", {
        type: "error",
        duration: 4000,
      });
    } finally {
      await waitMinLoading(submitter);
      setLoading(submitter, false);
      form.dataset.submitting = "0";
    }
  }


  // ----------------------------
  // Init
  // ----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    initTabs();


    const scrollKey = `personne-detail-scroll:${window.location.pathname}`;

    window.addEventListener("beforeunload", () => {
      sessionStorage.setItem(scrollKey, String(window.scrollY || 0));
    });

    const savedScroll = sessionStorage.getItem(scrollKey);
    if (savedScroll !== null) {
      window.scrollTo({ top: parseInt(savedScroll, 10) || 0, behavior: "auto" });
    }

    window.Toast = { show: toastShow };
    window.Modal = {
      confirm: modalConfirm,
      prompt: modalPrompt,
      close: modalClose,
      openHtml: modalOpenHtml,
      confirmHtml: modalConfirmHtml,
    };
  });
})();
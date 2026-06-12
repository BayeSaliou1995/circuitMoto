// static/circuitMoto/admin/js/dashboard.js

document.addEventListener("DOMContentLoaded", function () {
  // Reveal
  const items = document.querySelectorAll(".reveal");

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });

    items.forEach((el) => io.observe(el));
  } else {
    items.forEach((el) => el.classList.add("is-visible"));
  }

  // Voir plus / voir moins
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".btn-toggle-more");
    if (!btn) return;

    const panel = btn.closest(btn.dataset.targetClosest || ".panel");
    if (!panel) return;

    const extras = panel.querySelectorAll(".is-extra");
    const expanded = btn.dataset.expanded === "1";

    extras.forEach((el) => {
      el.style.display = expanded ? "none" : "";
    });

    btn.dataset.expanded = expanded ? "0" : "1";
    btn.textContent = expanded
      ? (btn.dataset.labelMore || "Voir plus")
      : (btn.dataset.labelLess || "Voir moins");
  });

  // Masquer les éléments extra au chargement
  document.querySelectorAll(".is-extra").forEach((el) => {
    el.style.display = "none";
  });

  // Pagination AJAX
  const sectionMap = {
    recents: "#dashboard-recents-container",
    documents: "#dashboard-documents-container",
    contacts: "#dashboard-contacts-container",
    newsletter: "#dashboard-newsletter-container",
  };

  async function loadDashboardSection(section, page) {
    const containerSelector = sectionMap[section];
    if (!containerSelector) return;

    const container = document.querySelector(containerSelector);
    if (!container) return;

    container.classList.add("is-loading");

    const url = new URL(window.location.href);
    url.searchParams.set("section", section);

    if (section === "recents") url.searchParams.set("recents_page", page);
    if (section === "documents") url.searchParams.set("docs_page", page);
    if (section === "contacts") url.searchParams.set("contacts_page", page);
    if (section === "newsletter") url.searchParams.set("newsletter_page", page);

    try {
      const response = await fetch(url.toString(), {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        }
      });

      if (!response.ok) {
        throw new Error("Erreur de chargement");
      }

      const html = await response.text();
      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = '<div class="empty-state"><p>Impossible de charger cette section.</p></div>';
    } finally {
      container.classList.remove("is-loading");
    }
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".ajax-page-btn");
    if (!btn) return;

    e.preventDefault();
    const section = btn.dataset.section;
    const page = btn.dataset.page || "1";
    loadDashboardSection(section, page);
  });
});
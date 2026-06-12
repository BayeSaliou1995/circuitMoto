// static/circuitMoto/js/nav.js
/* static/circuitMoto/js/nav.js */

// static/circuitMoto/js/nav.js

document.addEventListener("DOMContentLoaded", function () {
  const navWrap = document.querySelector(".site-nav-wrap");
  const emailFlagsUrl = navWrap ? navWrap.dataset.emailFlagsUrl : "";
  const isCircuitDetail = navWrap ? navWrap.dataset.isCircuitDetail === "1" : false;

  const nav = document.querySelector(".site-nav");
  const btn = document.querySelector(".menu-toggle");
  const panel = document.getElementById("mobileMenu");
  const overlay = document.querySelector(".nav-overlay");
  const body = document.body;
  const root = document.documentElement;

  const themeToggleDesktop = document.getElementById("theme-toggle");
  const themeToggleMobile = document.getElementById("theme-toggle-mobile");
  const themeButtons = [themeToggleDesktop, themeToggleMobile].filter(Boolean);

  // -----------------------------------
  // Scroll nav shadow
  // -----------------------------------
  function onScroll() {
    if (!nav) return;
    if (window.scrollY > 6) nav.classList.add("scrolled");
    else nav.classList.remove("scrolled");
  }

  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  // -----------------------------------
  // Theme management
  // -----------------------------------
  function getStoredTheme() {
    try {
      return localStorage.getItem("theme");
    } catch (err) {
      return null;
    }
  }

  function getPreferredTheme() {
    const stored = getStoredTheme();
    if (stored === "dark" || stored === "light") return stored;

    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function updateThemeButtons(theme) {
    themeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      button.setAttribute(
        "title",
        theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"
      );
      button.setAttribute(
        "aria-label",
        theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"
      );
    });
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    updateThemeButtons(theme);

    try {
      localStorage.setItem("theme", theme);
    } catch (err) {}
  }

  function toggleTheme() {
    const current = root.getAttribute("data-theme") || getPreferredTheme();
    applyTheme(current === "dark" ? "light" : "dark");
  }

  themeButtons.forEach((button) => {
    button.addEventListener("click", toggleTheme);
  });

  updateThemeButtons(root.getAttribute("data-theme") || getPreferredTheme());

  // -----------------------------------
  // Language switch: keep the same page, but move in/out of the /en/ prefix.
  // -----------------------------------
  function stripLanguagePrefix(pathname) {
    const cleanPath = pathname || "/";
    const stripped = cleanPath.replace(/^\/(fr|en)(?=\/|$)/i, "") || "/";
    return stripped.startsWith("/") ? stripped : `/${stripped}`;
  }

  function localizedNextUrl(targetLanguage) {
    const basePath = stripLanguagePrefix(window.location.pathname);
    const query = window.location.search || "";
    const hash = window.location.hash || "";

    if (targetLanguage === "en") {
      return `/en${basePath === "/" ? "/" : basePath}${query}${hash}`;
    }

    return `${basePath}${query}${hash}`;
  }

  document.addEventListener("click", (e) => {
    const button = e.target.closest(
      ".lang-form button[name='language'], .mobile-lang-form button[name='language']"
    );
    if (!button || !button.form) return;
    button.form.dataset.selectedLanguage = button.value;
  });

  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form || !form.matches || !form.matches(".lang-form, .mobile-lang-form")) return;

    const submitter = e.submitter && e.submitter.name === "language" ? e.submitter : null;
    const targetLanguage =
      (submitter && submitter.value) ||
      form.dataset.selectedLanguage ||
      (form.querySelector("button[name='language'].active") || {}).value ||
      "fr";

    const nextInput = form.querySelector("input[name='next']");
    if (nextInput) {
      nextInput.value = localizedNextUrl(targetLanguage);
    }
  });

  // -----------------------------------
  // Mobile menu
  // -----------------------------------
  function openMenu() {
    if (!panel || !overlay || !btn) return;
    panel.removeAttribute("hidden");
    overlay.removeAttribute("hidden");
    btn.setAttribute("aria-expanded", "true");
    body.classList.add("menu-open");
    document.documentElement.style.overflow = "hidden";
  }

  function closeMenu() {
    if (!panel || !overlay || !btn) return;
    btn.setAttribute("aria-expanded", "false");
    body.classList.remove("menu-open");

    setTimeout(() => {
      panel.setAttribute("hidden", "");
      overlay.setAttribute("hidden", "");
      document.documentElement.style.overflow = "";
    }, 300);
  }

  if (btn) {
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") === "true";
      open ? closeMenu() : openMenu();
    });
  }

  if (overlay) overlay.addEventListener("click", closeMenu);

  if (panel) {
    panel.addEventListener("click", (e) => {
      const a = e.target.closest("a,button");
      if (!a) return;

      if (
        a.classList.contains("menu-toggle") ||
        a.closest("summary") ||
        a.classList.contains("mobile-theme-toggle")
      ) {
        return;
      }

      closeMenu();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && body.classList.contains("menu-open")) {
      closeMenu();
    }
  });

  // -----------------------------------
  // Desktop dropdowns
  // -----------------------------------
  const navDDs = document.querySelectorAll(".nav-dd");

  document.addEventListener("click", (e) => {
    navDDs.forEach((dd) => {
      if (dd.open && !dd.contains(e.target)) dd.removeAttribute("open");
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      navDDs.forEach((dd) => dd.removeAttribute("open"));
    }
  });

  // -----------------------------------
  // Mobile dropdowns
  // -----------------------------------
  document.addEventListener("click", (e) => {
    document.querySelectorAll(".mobile-dd[open]").forEach((dd) => {
      const inside = dd.contains(e.target);
      const isSummary = e.target.closest("summary");
      if (!inside && !isSummary) dd.removeAttribute("open");
    });
  });

  // -----------------------------------
  // CSRF helper
  // -----------------------------------
  function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  // -----------------------------------
  // Email flags AJAX
  // -----------------------------------
  document.addEventListener("change", (e) => {
    const t = e.target.closest(".email-flag");
    if (!t || !emailFlagsUrl) return;

    fetch(emailFlagsUrl, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-CSRFToken": getCsrf()
      },
      body: new URLSearchParams({
        key: t.dataset.key,
        value: t.checked ? "1" : "0"
      })
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.ok) {
          t.checked = !t.checked;
          if (window.UI?.toast) {
            window.UI.toast(data.message || "Mise à jour impossible.", {
              type: "error",
              duration: 3200
            });
          } else {
            alert(data.message || "Mise à jour impossible.");
          }
        }
      })
      .catch(() => {
        t.checked = !t.checked;
        if (window.UI?.toast) {
          window.UI.toast("Erreur réseau.", {
            type: "error",
            duration: 3200
          });
        } else {
          alert("Erreur réseau.");
        }
      });
  });

  // -----------------------------------
  // Last circuit storage
  // -----------------------------------
  const STORAGE_KEY = "lastCircuitCode";

  document.addEventListener("click", (e) => {
    const a = e.target.closest("a.circuit-link[data-code]");
    if (!a) return;
    try {
      localStorage.setItem(STORAGE_KEY, a.dataset.code);
    } catch (err) {}
  });

  if (isCircuitDetail) {
    try {
      const m = location.pathname.match(/\/circuit\/([^/]+)\/?/i);
      if (m && m[1]) localStorage.setItem(STORAGE_KEY, decodeURIComponent(m[1]));
    } catch (err) {}
  }

  function markLast() {
    let last = null;
    try {
      last = localStorage.getItem(STORAGE_KEY);
    } catch (err) {}

    if (!last) return;

    document.querySelectorAll(".dd-item.circuit-link[data-code]").forEach((a) => {
      if (a.dataset.code === last) {
        a.classList.add("is-last-selected");
        if (!a.querySelector(".badge-last")) {
          const badge = document.createElement("span");
          badge.className = "badge-last";
          badge.textContent = "Dernier consulté";
          const container = a.querySelector("div") || a;
          container.appendChild(badge);
        }
      } else {
        a.classList.remove("is-last-selected");
        const b = a.querySelector(".badge-last");
        if (b) b.remove();
      }
    });

    document.querySelectorAll(".mobile-link.circuit-link[data-code]").forEach((a) => {
      if (a.dataset.code === last) {
        a.classList.add("is-last-selected");
        if (!a.querySelector(".badge-last")) {
          const badge = document.createElement("span");
          badge.className = "badge-last";
          badge.textContent = "Dernier consulté";
          a.appendChild(badge);
        }
      } else {
        a.classList.remove("is-last-selected");
        const b = a.querySelector(".badge-last");
        if (b) b.remove();
      }
    });
  }

  function normPath(p) {
    return (p || "/").replace(/\/+$/, "");
  }

  function isSameCircuit(href) {
    const u = new URL(href, location.origin);
    if (u.origin !== location.origin) return false;
    const tgt = normPath(u.pathname);
    const cur = normPath(location.pathname);
    return /^\/circuit\/[^/]+\/?$/.test(tgt) && tgt === cur;
  }

  document.addEventListener("click", (e) => {
    const a = e.target.closest("a.circuit-link");
    if (!a) return;

    if (isSameCircuit(a.getAttribute("href"))) {
      e.preventDefault();
      document.querySelectorAll(".nav-dd[open]").forEach((dd) => dd.removeAttribute("open"));
      body.classList.remove("menu-open");
    }
  });

  function markCurrentInMenus() {
    const cur = normPath(location.pathname);

    document.querySelectorAll("a.circuit-link").forEach((a) => {
      const p = normPath(new URL(a.href, location.origin).pathname);
      if (p === cur) {
        a.setAttribute("aria-current", "page");
        a.classList.add("is-last-selected");
      } else {
        a.removeAttribute("aria-current");
        a.classList.remove("is-last-selected");
      }
    });
  }

  markLast();
  markCurrentInMenus();

  document.addEventListener(
    "toggle",
    (e) => {
      const dd = e.target;
      if (dd.matches && dd.matches(".nav-dd") && dd.open) {
        markLast();
      }
    },
    true
  );
});

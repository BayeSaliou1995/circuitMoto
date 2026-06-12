/* static/circuitMoto/js/circuit_home.js */
(function () {
  'use strict';

  const CONFIG = {
    typewriterSpeed: 70,
    typewriterDelay: 2000,
    counterSpeed: 2000,
    modalAnimation: 220,
    filtersDebounce: 250
  };

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  const prefersReducedMotion = () =>
    window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const safeJSON = (text, fallback) => {
    try { return JSON.parse(text); } catch (e) { return fallback; }
  };

  const cssEscape = (v) => {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(v);
    return String(v).replace(/["\\]/g, '\\$&');
  };

  // =========================
  // Typewriter
  // =========================
  class Typewriter {
    constructor(container) {
      this.container = container;
      this.textElement = container.querySelector('.typewriter-text');
      this.dataNode = container.querySelector('.typewriter-data');
      this.data = safeJSON(this.dataNode ? this.dataNode.textContent : '[]', []);
      this.currentText = 0;
      this.currentChar = 0;
      this.isDeleting = false;
      this.timer = null;

      if (!this.textElement || !this.data.length || prefersReducedMotion()) return;
      this.type();
    }

    type() {
      const s = this.data[this.currentText] || '';
      const next = this.isDeleting
        ? s.substring(0, Math.max(0, this.currentChar - 1))
        : s.substring(0, this.currentChar + 1);

      this.textElement.textContent = next;
      this.currentChar = next.length;

      let speed = CONFIG.typewriterSpeed;
      if (this.isDeleting) speed = Math.max(20, speed / 2);

      if (!this.isDeleting && this.currentChar === s.length) {
        speed = CONFIG.typewriterDelay;
        this.isDeleting = true;
      } else if (this.isDeleting && this.currentChar === 0) {
        this.isDeleting = false;
        this.currentText = (this.currentText + 1) % this.data.length;
        speed = 450;
      }

      this.timer = setTimeout(() => this.type(), speed);
    }
  }

  // =========================
  // Counter
  // =========================
  class Counter {
    constructor(el) {
      this.el = el;
      this.target = parseInt(el.dataset.target, 10) || 0;
      this.duration = CONFIG.counterSpeed;

      if (el.dataset.counterInitialized) return;
      el.dataset.counterInitialized = '1';

      if (prefersReducedMotion()) {
        el.textContent = this.target.toLocaleString();
        return;
      }
      this.animate();
    }

    animate() {
      const start = performance.now();
      const tick = (t) => {
        const p = Math.min((t - start) / this.duration, 1);
        const val = Math.floor(p * this.target);
        this.el.textContent = val.toLocaleString();
        if (p < 1) requestAnimationFrame(tick);
        else this.el.textContent = this.target.toLocaleString();
      };
      requestAnimationFrame(tick);
    }
  }

  // =========================
  // Modal
  // =========================
  class ModalManager {
    constructor() {
      this.modal = $('[data-quick-view-modal="true"]');
      this.modalBody = $('[data-modal-body="true"]');
      this.closeEls = this.modal ? $$('[data-modal-close="true"]', this.modal) : [];
      this.lastFocus = null;

      if (!this.modal || !this.modalBody) return;
      this.init();
    }

    init() {
      this.closeEls.forEach(el => el.addEventListener('click', () => this.close()));

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.modal.dataset.active === 'true') this.close();
      }, { passive: true });
    }

    open(html) {
      this.lastFocus = document.activeElement;

      this.modalBody.innerHTML = html;
      this.modal.dataset.active = 'true';
      this.modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';

      $$('[data-counter="true"]', this.modalBody).forEach(el => new Counter(el));
      this.initScrollFades();

      const btn = $('.modal-close', this.modal);
      if (btn) btn.focus({ preventScroll: true });
    }

    close() {
      this.modal.dataset.active = 'false';
      this.modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';

      const cleanup = () => { this.modalBody.innerHTML = ''; };
      if (prefersReducedMotion()) cleanup();
      else setTimeout(cleanup, CONFIG.modalAnimation);

      if (this.lastFocus && this.lastFocus.focus) {
        this.lastFocus.focus({ preventScroll: true });
      }
    }

    initScrollFades() {
      const nodes = $$('.scroll-fade', this.modalBody);

      const update = (node) => {
        const atBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 2;
        node.dataset.atBottom = atBottom ? '1' : '0';
      };

      nodes.forEach(node => {
        node.addEventListener('scroll', () => update(node), { passive: true });
        update(node);
      });
    }
  }

  // =========================
  // Helpers
  // =========================
  const debounce = (fn, wait) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  };

  const makeRipple = (e, el) => {
    if (prefersReducedMotion()) return;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') return;

    const old = el.querySelector('.ripple');
    if (old) old.remove();

    const rect = el.getBoundingClientRect();
    const x = (e.clientX || rect.left + rect.width / 2) - rect.left;
    const y = (e.clientY || rect.top + rect.height / 2) - rect.top;

    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    el.appendChild(ripple);

    setTimeout(() => ripple.remove(), 650);
  };

  // =========================
  // Circuit Grid
  // =========================
  class CircuitGrid {
    constructor() {
      this.filters = $('#filters');
      this.activeFilters = $('[data-active-filters="true"]');
      this.resetButton = $('[data-reset-filters="true"]');
      this.modal = new ModalManager();

      this.init();
    }

    init() {
      $$('[data-counter="true"]').forEach(el => new Counter(el));
      this.initProgressBars();
      this.initAccordions();
      this.initQuickView();
      this.initFilters();
      this.initEditForm();
      this.initTypewriter();
      this.initRipple();
      this.initAnchors();
    }

    initProgressBars() {
      $$('[data-progress="true"]').forEach(bar => {
        const pct = Math.max(0, Math.min(100, parseFloat(bar.dataset.percent || '0')));
        const fill = bar.querySelector('.progress-fill');
        if (!fill) return;

        fill.style.width = '0%';
        const run = () => { fill.style.width = pct + '%'; };
        if (prefersReducedMotion()) run();
        else setTimeout(run, 250);
      });
    }

    initAccordions() {
      $$('[data-accordion-trigger="true"]').forEach(trigger => {
        const content = trigger.nextElementSibling;
        if (!content) return;

        trigger.addEventListener('click', () => {
          const expanded = trigger.getAttribute('aria-expanded') === 'true';
          trigger.setAttribute('aria-expanded', String(!expanded));
          content.style.maxHeight = expanded ? '0' : content.scrollHeight + 'px';
        });
      });
    }

    initQuickView() {
      $$('[data-quick-view="true"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();

          const id = btn.dataset.circuitId;
          const tpl = id ? document.getElementById(`qv-${id}`) : null;
          if (!tpl) return;

          this.modal.open(tpl.innerHTML);
        });
      });
    }

    initFilters() {
      if (!this.filters || !this.activeFilters) return;

      const chipsWrap = $('.filter-chips', this.activeFilters);
      const apply = () => {
        const fd = new FormData(this.filters);
        const actives = [];

        for (const [k, v] of fd.entries()) {
          if (!v) continue;
          if (k === 'page') continue;
          actives.push({ key: k, value: String(v) });
        }

        if (!actives.length) {
          this.activeFilters.hidden = true;
          if (this.resetButton) this.resetButton.disabled = true;
          if (chipsWrap) chipsWrap.innerHTML = '';
          return;
        }

        this.activeFilters.hidden = false;
        if (chipsWrap) chipsWrap.innerHTML = '';

        actives.forEach(({ key, value }) => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'filter-chip';
          chip.textContent = `${this.getFilterLabel(key)}: ${value}`;

          chip.addEventListener('click', () => {
            const input = this.filters.querySelector(`[name="${cssEscape(key)}"]`);
            if (!input) return;

            if (input.tagName === 'SELECT') input.selectedIndex = 0;
            else input.value = '';

            this.filters.submit();
          });

          if (chipsWrap) chipsWrap.appendChild(chip);
        });

        if (this.resetButton) this.resetButton.disabled = false;
      };

      const debouncedSubmit = debounce(() => this.filters.submit(), CONFIG.filtersDebounce);

      $$('input, select', this.filters).forEach(el => {
        el.addEventListener('input', () => { apply(); debouncedSubmit(); });
        el.addEventListener('change', () => { apply(); debouncedSubmit(); });
      });

      if (this.resetButton) {
        this.resetButton.addEventListener('click', () => {
          this.filters.reset();
          this.filters.submit();
        });
      }

      apply();
    }

    // ⚠️ Ici tu avais du Django {% trans %} dans le JS inline.
    // Une fois séparé en .js, Django ne rend plus ces tags.
    // Donc on met des libellés “simples” côté JS.
    // Si tu veux i18n parfait: je te donne la version Django/JSON dans la prochaine étape.
    getFilterLabel(key) {
      const labels = {
        q: 'Recherche',
        from: 'Date',
        sort: 'Tri'
      };
      return labels[key] || key;
    }

    initEditForm() {
      const form = $('#edit-form');
      const input = $('#ref');
      if (!form || !input) return;

      const base = form.dataset.editUrl || (window.location.origin + '/inscription/edit/');

      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const ref = input.value.trim();
        if (!ref) return;

        const url = new URL(base, window.location.origin);
        url.searchParams.set('ref', ref);
        window.location.href = url.toString();
      });
    }

    initTypewriter() {
      $$('.typewriter-container').forEach(c => new Typewriter(c));
    }

    initRipple() {
      $$('[data-ripple="true"]').forEach(el => {
        el.addEventListener('pointerdown', (e) => makeRipple(e, el));
      });
    }

    initAnchors() {
      $$('a[href^="#"]').forEach(a => {
        a.addEventListener('click', (e) => {
          const href = a.getAttribute('href');
          if (!href || href === '#') return;

          const target = document.querySelector(href);
          if (!target) return;

          e.preventDefault();
          target.scrollIntoView({
            behavior: prefersReducedMotion() ? 'auto' : 'smooth',
            block: 'start'
          });
        });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    new CircuitGrid();
  });
})();

(function () {
  const section = document.querySelector('[data-filters-section="true"]');
  if (!section) return;

  const card = section.querySelector('[data-filter-card="true"]');
  const panel = section.querySelector('[data-filters-panel="true"]');
  const toggleBtn = section.querySelector('[data-filter-toggle="true"]');
  const closeBtn = section.querySelector('[data-filter-close="true"]');
  const overlay = section.querySelector('[data-filters-overlay="true"]');
  const form = section.querySelector('#filters');

  const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

  function lockBody(lock) {
    document.documentElement.classList.toggle('no-scroll', !!lock);
    document.body.classList.toggle('no-scroll', !!lock);
  }

    function openFilters() {
    card.dataset.open = 'true';
    toggleBtn.setAttribute('aria-expanded', 'true');
    panel.hidden = false;

    // Plus de popup => pas d'overlay, pas de lock scroll
    if (overlay) overlay.hidden = true;
    lockBody(false);

    const first = form?.querySelector('input, select, button, textarea');
    setTimeout(() => first?.focus?.(), 50);
    }

    function closeFilters() {
    card.dataset.open = 'false';
    toggleBtn.setAttribute('aria-expanded', 'false');
    panel.hidden = true;

    if (overlay) overlay.hidden = true;
    lockBody(false);

    toggleBtn.focus();
    }


  // État initial : fermé
  card.dataset.open = 'false';
  panel.hidden = true;
  overlay.hidden = true;

  toggleBtn.addEventListener('click', () => {
    const open = card.dataset.open === 'true';
    open ? closeFilters() : openFilters();
  });

  closeBtn?.addEventListener('click', closeFilters);
  overlay?.addEventListener('click', closeFilters);

  // ESC pour fermer (recommandé)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && card.dataset.open === 'true') closeFilters();
  });

  // Si on passe desktop <-> mobile pendant ouvert
  window.addEventListener('resize', () => {
    if (card.dataset.open === 'true' && !isMobile()) {
      lockBody(false);
      overlay.hidden = true;
    }
  });
})();

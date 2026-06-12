'use strict';

/**
 * static/circuitMoto/js/home.i18n.js
 * circuitMoto-home.i18n.js
 * ————————————————————————————————————————————————————————
 * Prérequis : charger d'abord le catalogue i18n JS de Django
 *   <script src="{% url 'javascript-catalog' %}"></script>
 * puis inclure CE FICHIER (de préférence en defer).
 *
 * Ce bundle regroupe : helpers i18n, utils, CircuitList, TypeWriter,
 * TitleParticles, QuickViewPremium (+ observer unique) et le boot.
 */

(function () {
    // ——————————————————————————————————————
    // i18n helpers (fallbacks si le catalogue n'est pas prêt)
    // ——————————————————————————————————————
    //   const __   = (s) => (window.gettext    ? window.gettext(s)    : s);
    //   const __n  = (s, p, n) => (window.ngettext  ? window.ngettext(s, p, n)  : (n === 1 ? s : p));
    //   const __p  = (ctx, s) => (window.pgettext  ? window.pgettext(ctx, s)  : s);
    //   const __np = (ctx, s, p, n) => (window.npgettext ? window.npgettext(ctx, s, p, n) : (n === 1 ? s : p));
    //   const __i  = (fmt, vars) => (window.interpolate ? window.interpolate(fmt, vars, true) : fmt);



    // Fallbacks sûrs (évite "ReferenceError: gettext is not defined")
    // const gettext     = (window.gettext     || ((s)=>s));
    const ngettext    = (window.ngettext    || ((s,p,n)=> (n===1?s:p)));
    const pgettext    = (window.pgettext    || ((ctx,s)=>s));
    const npgettext   = (window.npgettext   || ((ctx,s,p,n)=> (n===1?s:p)));
    const interpolate = (window.interpolate || ((fmt, vars)=> fmt));
    const gettext     = (window.gettext || ((s)=>s));


    // Utils "filtres actifs ?" (ignore la pagination)
    function _hasActiveFilters() {
      const p = new URLSearchParams(window.location.search);
      p.delete('page');
      return Array.from(p.keys()).length > 0;
    }

    document.addEventListener('DOMContentLoaded', () => {
      const resetBtn = document.querySelector('[data-reset-filters="true"]');
      if (!resetBtn) return;

      // état initial
      resetBtn.setAttribute('aria-disabled', String(!_hasActiveFilters()));

      // action reset
      resetBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (resetBtn.getAttribute('aria-disabled') === 'true') return; // ignore si "désactivé" visuellement
        const clean = new URL(window.location.href);
        clean.search = '';
        clean.hash = 'circuits';
        window.location.assign(clean.toString());
      });

      // si tu veux être tatillon: mettre à jour l'état au back/forward
      window.addEventListener('popstate', () => {
        resetBtn.setAttribute('aria-disabled', String(!_hasActiveFilters()));
      });
    });


  // ——————————————————————————————————————
  // Utils génériques
  // ——————————————————————————————————————
  const debounce = (fn, wait = 150) => {
    let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn.apply(null, args), wait); };
  };

  function isValidUUID(uuid) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(uuid);
  }

  function showNotification(message, type = 'info') {
    const n = document.createElement('div');
    n.className = `notification notification-${type}`;
    n.textContent = message;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 5000);
  }

  function initTiltEffect() {
    const elements = document.querySelectorAll('[data-tilt="true"]');
    elements.forEach(element => {
      element.addEventListener('mousemove', (e) => {
        const { left, top, width, height } = element.getBoundingClientRect();
        const x = (e.clientX - left) / width;
        const y = (e.clientY - top) / height;
        const rotateX = (y - 0.5) * 10;
        const rotateY = (x - 0.5) * -10;
        element.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
      });
      element.addEventListener('mouseleave', () => {
        element.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1, 1, 1)';
      });
    });
  }

  // ——————————————————————————————————————
  // CircuitList
  // ——————————————————————————————————————
  class CircuitList {
    constructor(container) {
      this.container = container;
      this.serverMode = !!document.getElementById('filters')?.dataset?.server;
      this.circuits = [];
      this.filters = { search: '', date: '', sort: 'date' };
      this.lastFocused = null; // pour restaurer le focus après le modal
      this.init();
    }

    init() {
      this.loadCircuits();
      this.bindEvents();
      if (!this.serverMode) {
        this.syncInitialFilters();
        this.applyFilters();
      }
      this.initAnimations();
    }

    loadCircuits() {
      this.circuits = Array.from(this.container.querySelectorAll('[data-circuit="true"]'));
      if (!this.serverMode) this.applyFilters();
    }

    bindEvents() {
      // Recherche (debounce)
      const searchInput = this.container.querySelector('[data-search-input="true"]');
      if (searchInput && !this.serverMode) {
        searchInput.addEventListener('input', debounce((e) => {
          this.filters.search = (e.target.value || '').toLowerCase();
          this.applyFilters();
        }, 180));
      }

      // Filtre par date
      const dateInput = this.container.querySelector('[data-date-filter="true"]');
      if (dateInput && !this.serverMode) {
        dateInput.addEventListener('change', (e) => {
          this.filters.date = e.target.value || '';
          this.applyFilters();
        });
      }

      // — Tri (client) —
      const sortSelect = this.container.querySelector('[data-sort-select="true"]');
      if (sortSelect && !this.serverMode) {
        sortSelect.addEventListener('change', (e) => {
          this.filters.sort = e.target.value || 'date';
          this.applyFilters();
        });
      }

      // — Réinitialiser (client) —
      const resetBtn = this.container.querySelector('[data-reset-filters="true"]');
      if (resetBtn && !this.serverMode) {
        resetBtn.addEventListener('click', () => this.resetFilters());
      }

      // Accordéon
      this.container.querySelectorAll('[data-accordion-trigger="true"]').forEach(trigger => {
        trigger.addEventListener('click', () => this.toggleAccordion(trigger));
      });

      // Ripple
      this.container.querySelectorAll('[data-ripple="true"]').forEach(btn => {
        btn.addEventListener('click', this.createRipple.bind(this));
      });

      // Aperçu rapide
      this.container.querySelectorAll('[data-quick-view="true"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          this.lastFocused = document.activeElement;
          this.showQuickView(btn.dataset.circuitId, btn);
        });
      });

      // Fermer modal
      this.container.querySelectorAll('[data-modal-close="true"]').forEach(btn => {
        btn.addEventListener('click', () => this.hideQuickView());
      });

      // ESC pour fermer
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') this.hideQuickView();
      });
    }

    applyFilters() {
      if (this.serverMode) return;
      const search = this.filters.search;
      const dateFilter = this.filters.date;

      this.circuits.forEach(circuit => {
        const name = (circuit.dataset.name || '').toLowerCase();
        const cDate = circuit.dataset.date || '';
        const matchesSearch = !search || name.includes(search);
        const matchesDate = !dateFilter || (cDate >= dateFilter);
        const isVisible = matchesSearch && matchesDate;

        if (isVisible) {
          circuit.style.display = '';
          circuit.style.animation = 'cardEntrance 0.6s ease-out';
        } else {
          circuit.style.display = 'none';
        }
      });

      this.sortCircuits();
      this.updateActiveFilters();
      this.checkEmptyState();
    }

    sortCircuits() {
      const grid = this.container.querySelector('[data-circuit-grid="true"]');
      if (!grid) return;

      const visible = this.circuits.filter(c => c.style.display !== 'none');
      const sorted = [...visible].sort((a, b) => {
        const aPrice = Number(a.dataset.price || 0);
        const bPrice = Number(b.dataset.price || 0);
        const aCap = Number(a.dataset.capacity || 0);
        const bCap = Number(b.dataset.capacity || 0);
        const aIns = Number(a.dataset.inscriptions || 0);
        const bIns = Number(b.dataset.inscriptions || 0);

        const aAvail = aCap - aIns;
        const bAvail = bCap - bIns;

        switch (this.filters.sort) {
          case 'price_asc':  return aPrice - bPrice;
          case 'price_desc': return bPrice - aPrice;
          case 'capacity':   return bAvail - aAvail;
          default: {
            const ad = new Date(a.dataset.sortDate || a.dataset.date || 0).getTime();
            const bd = new Date(b.dataset.sortDate || b.dataset.date || 0).getTime();
            return ad - bd;
          }
        }
      });

      sorted.forEach(c => grid.appendChild(c));
    }

    resetFilters() {
      this.filters = { search: '', date: '', sort: 'date' };

      const searchInput = this.container.querySelector('[data-search-input="true"]');
      const dateInput   = this.container.querySelector('[data-date-filter="true"]');
      const sortSelect  = this.container.querySelector('[data-sort-select="true"]');

      if (searchInput) searchInput.value = '';
      if (dateInput)   dateInput.value   = '';
      if (sortSelect)  sortSelect.value  = 'date';

      const resetBtn = this.container.querySelector('[data-reset-filters="true"]');
      if (resetBtn) { resetBtn.disabled = true; resetBtn.setAttribute('aria-disabled','true'); }

      this.applyFilters();
    }

    toggleAccordion(trigger) {
      const expanded = trigger.getAttribute('aria-expanded') === 'true';
      trigger.setAttribute('aria-expanded', String(!expanded));
      const content = trigger.nextElementSibling;
      if (content && content.matches('[data-accordion-content="true"]')) {
        content.style.maxHeight = !expanded ? content.scrollHeight + 'px' : '0';
      }
    }

    createRipple(event) {
      const btn = event.currentTarget;
      const prev = btn.querySelector('.ripple');
      if (prev) prev.remove();

      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const circle = document.createElement('span');
      circle.className = 'ripple';
      circle.style.width = circle.style.height = `${size}px`;
      circle.style.left = `${event.clientX - rect.left - size/2}px`;
      circle.style.top  = `${event.clientY - rect.top  - size/2}px`;

      btn.appendChild(circle);
      circle.addEventListener('animationend', () => circle.remove());
    }

    showQuickView(circuitId, triggerEl = null) {
      const modal = this.container.querySelector('[data-quick-view-modal="true"]');
      const modalBody = this.container.querySelector('[data-modal-body="true"]');
      if (!modal || !modalBody) return;

      // A11y & lock scroll
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('data-active', 'true');
      document.documentElement.style.overflow = 'hidden';
      this.lastFocused = triggerEl || document.activeElement;

      // Loading
      modalBody.innerHTML = `
        <div class="quick-view-loading">
          <div class="loading-spinner"></div>
          <p>${gettext('Chargement des détails du circuit…')}</p>
        </div>
      `;

      // Injection depuis <template id="qv-<id>">
      const tpl = document.getElementById(`qv-${circuitId}`);
      setTimeout(() => {
        if (tpl) {
          modalBody.innerHTML = tpl.innerHTML;
          const focusable = modal.querySelector('.qv-title') || modal.querySelector('.modal-close');
          if (focusable) { focusable.setAttribute('tabindex', '-1'); focusable.focus(); }
        } else {
          modalBody.innerHTML = `
            <div class="quick-view-content">
              <h3>${gettext('Détails du circuit')}</h3>
              <p>${gettext('Impossible de charger les informations de ce circuit.')}</p>
            </div>
          `;
        }
      }, 200);
    }

    hideQuickView() {
      const modal = this.container.querySelector('[data-quick-view-modal="true"]');
      const modalBody = this.container.querySelector('[data-modal-body="true"]');
      if (!modal) return;
      modal.setAttribute('data-active', 'false');
      modal.removeAttribute('aria-modal');
      document.documentElement.style.overflow = '';
      if (modalBody) modalBody.innerHTML = '';
      if (this.lastFocused && typeof this.lastFocused.focus === 'function') {
        this.lastFocused.focus();
      }
    }

    updateActiveFilters() {
      const activeFiltersContainer = this.container.querySelector('[data-active-filters="true"]');
      const filterChips = this.container.querySelector('.filter-chips');
      if (!activeFiltersContainer || !filterChips) return;

      const activeFilters = [];
      if (this.filters.search) activeFilters.push(`${gettext('Recherche')}: "${this.filters.search}"`);
      if (this.filters.date)   activeFilters.push(`${gettext('À partir du')}: ${this.filters.date}`);
      if (this.filters.sort && this.filters.sort !== 'date') {
        const sel = this.container.querySelector('[data-sort-select="true"]');
        if (sel) activeFilters.push(`${gettext('Tri')}: ${sel.options[sel.selectedIndex].text}`);
      }

      filterChips.innerHTML = activeFilters.map(f => `<span class="filter-chip">${f}</span>`).join('');

      // const resetBtn = this.container.querySelector('[data-reset-filters="true"]');
      const hasActive = activeFilters.length > 0;
      const resetBtn = document.querySelector('[data-reset-filters="true"]');
      if (resetBtn) {
        resetBtn.removeAttribute('disabled'); // ⚠️ crucial
        resetBtn.setAttribute('aria-disabled', String(!_hasActiveFilters()));
        resetBtn.addEventListener('click', /* même code que ci-dessus */);
      }

      activeFiltersContainer.hidden = !hasActive;
    }

    checkEmptyState() {
      const visibleCount = this.circuits.filter(c => c.style.display !== 'none').length;
      const emptyState = this.container.querySelector('[data-empty-state="true"]');
      if (emptyState) emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
    }

    initAnimations() {
      this.animateCounters();
      this.initMotoAnimation();
      this.initParallax();
    }

    animateCounters() {
      const counters = this.container.querySelectorAll('[data-counter="true"]');
      counters.forEach(counter => {
        const target = parseInt(counter.dataset.target || '0', 10);
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;
        const timer = setInterval(() => {
          current += step;
          if (current >= target) { current = target; clearInterval(timer); }
          counter.textContent = String(Math.floor(current));
        }, 16);
      });
    }

    initMotoAnimation() {
      const moto = this.container.querySelector('[data-moto-animation="true"]');
      if (!moto) return;
      moto.addEventListener('mouseenter', () => { moto.style.transform = 'scale(1.1)'; });
      moto.addEventListener('mouseleave', () => { moto.style.transform = 'scale(1)'; });
    }

    initParallax() {
      const mediaElements = this.container.querySelectorAll('[data-media-parallax="true"]');
      mediaElements.forEach(media => {
        media.addEventListener('mousemove', (e) => {
          const { left, top, width, height } = media.getBoundingClientRect();
          const x = (e.clientX - left) / width;
          const y = (e.clientY - top) / height;
          media.style.transform = `perspective(1000px) rotateX(${(y - 0.5) * 5}deg) rotateY(${(x - 0.5) * 5}deg)`;
        });
        media.addEventListener('mouseleave', () => {
          media.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
        });
      });
    }

    syncInitialFilters() {
      const s  = this.container.querySelector('[data-search-input="true"]');
      const d  = this.container.querySelector('[data-date-filter="true"]');
      const so = this.container.querySelector('[data-sort-select="true"]');
      this.filters.search = (s && s.value ? s.value.trim().toLowerCase() : '');
      this.filters.date   = (d && d.value ? d.value : '');
      this.filters.sort   = (so && so.value ? so.value : 'date');
      this.updateActiveFilters();
    }
  }

  // ——————————————————————————————————————
  // TypeWriter (machine à écrire)
  // ——————————————————————————————————————
  class TypeWriter {
    constructor(element) {
      this.element = element;
      this.texts = [];
      try { if (element.dataset.texts) this.texts = JSON.parse(element.dataset.texts); } catch (e) {}

      if (!this.texts.length) {
        const script = element.parentElement?.querySelector('script.typewriter-data');
        if (script?.textContent) {
          try { this.texts = JSON.parse(script.textContent.trim()); } catch (e) {}
        }
      }

      if (!this.texts.length) {
        this.texts = Array.from(this.element.querySelectorAll('[data-text]'))
          .map(n => (n.textContent || '').trim())
          .filter(Boolean);
      }
      this.currentText = 0;
      this.currentChar = 0;
      this.isDeleting = false;
      this.speed = 80;
      this.pause = 2000;
      this.init();
    }

    init() {
      if (this.texts.length === 0) return;
      setTimeout(() => { this.type(); }, 1500);
    }

    type() {
      const current = this.currentText % this.texts.length;
      const fullText = this.texts[current];

      if (this.isDeleting) {
        this.element.textContent = fullText.substring(0, this.currentChar - 1);
        this.currentChar--; this.speed = 50;
      } else {
        this.element.textContent = fullText.substring(0, this.currentChar + 1);
        this.currentChar++; this.speed = 80;
      }

      if (!this.isDeleting && this.currentChar === fullText.length) {
        this.isDeleting = true; this.speed = this.pause;
      } else if (this.isDeleting && this.currentChar === 0) {
        this.isDeleting = false; this.currentText++; this.speed = 500;
      }

      setTimeout(() => this.type(), this.speed);
    }
  }

  // ——————————————————————————————————————
  // TitleParticles (effets autour du titre)
  // ——————————————————————————————————————
  class TitleParticles {
    constructor(container) {
      this.container = container;
      this.particles = [];
      this.init();
    }

    init() { this.createParticles(); this.animate(); }

    createParticles() {
      const particleCount = 12;
      for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'title-particle';
        const angle = (i / particleCount) * Math.PI * 2;
        const distance = 60 + Math.random() * 40;
        const size = 3 + Math.random() * 4;
        particle.style.cssText = `
          position: absolute; width: ${size}px; height: ${size}px;
          background: linear-gradient(135deg, var(--primary), var(--secondary));
          border-radius: 50%; pointer-events: none;
          opacity: ${0.3 + Math.random() * 0.4}; filter: blur(${Math.random() * 2}px);
        `;
        this.container.appendChild(particle);
        this.particles.push({ element: particle, angle, distance, speed: 0.2 + Math.random() * 0.3, size, pulseSpeed: 2 + Math.random() * 3 });
      }
    }

    animate() {
      const centerX = this.container.offsetWidth / 2;
      const centerY = this.container.offsetHeight / 2;
      const time = Date.now() * 0.001;

      this.particles.forEach(p => {
        const x = centerX + Math.cos(p.angle + time * p.speed) * p.distance;
        const y = centerY + Math.sin(p.angle + time * p.speed * 0.7) * p.distance;
        const pulse = Math.sin(time * p.pulseSpeed) * 0.3 + 0.7;
        p.element.style.transform = `translate(${x}px, ${y}px) scale(${pulse})`;
        p.element.style.opacity = 0.2 + pulse * 0.3;
      });

      requestAnimationFrame(() => this.animate());
    }
  }

  // ——————————————————————————————————————
  // QuickViewPremium (exporte sur window, 1 seule instance d'observer)
  // ——————————————————————————————————————
  if (!window.QuickViewPremium) {
    window.QuickViewPremium = class {
      constructor(modalBody) { this.modalBody = modalBody; this.init(); }
      init() { this.initAnimations(); this.initScrollEffects(); this.initMagneticEffects(); this.initRippleEffects(); this.initAutoFocus(); }
      initAnimations() {
        const els = this.modalBody.querySelectorAll('.slide-in');
        els.forEach(el => {
          const d = parseInt(el.dataset.delay || '0');
          setTimeout(() => { el.style.animation = `slideInUp 0.6s ease ${d}ms forwards`; }, 50);
        });
      }
      initScrollEffects() {
        const texts = this.modalBody.querySelectorAll('.scroll-fade');
        const io = new IntersectionObserver(es => {
          es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('scrolled'); } });
        }, { threshold: 0.1 });
        texts.forEach(t => io.observe(t));
      }
      initMagneticEffects() {
        this.modalBody.querySelectorAll('.magnetic').forEach(el => {
          const s = parseFloat(el.dataset.strength) || 0.2;
          el.addEventListener('mousemove', e => {
            const r = el.getBoundingClientRect();
            const x = e.clientX - r.left - r.width / 2;
            const y = e.clientY - r.top - r.height / 2;
            el.style.transform = `translate(${x * s}px, ${y * s}px)`;
          });
          el.addEventListener('mouseleave', () => { el.style.transform = 'translate(0, 0)'; });
        });
      }
      initRippleEffects() {
        this.modalBody.querySelectorAll('[data-ripple="true"]').forEach(btn => {
          btn.addEventListener('click', this.createRipple.bind(this));
        });
      }
      createRipple(e) {
        const btn = e.currentTarget; const prev = btn.querySelector('.ripple'); if (prev) prev.remove();
        const r = btn.getBoundingClientRect(); const size = Math.max(r.width, r.height);
        const x = e.clientX - r.left - size / 2; const y = e.clientY - r.top - size / 2;
        const ripple = document.createElement('span'); ripple.className = 'ripple';
        ripple.style.width = ripple.style.height = `${size}px`; ripple.style.left = `${x}px`; ripple.style.top = `${y}px`;
        btn.appendChild(ripple); ripple.addEventListener('animationend', () => ripple.remove());
      }
      initAutoFocus() { const first = this.modalBody.querySelector('button, a, [tabindex]'); if (first) { setTimeout(() => first.focus(), 100); } }
    };
  }

  // ——————————————————————————————————————
  // Boot (DOMContentLoaded unique)
  // ——————————————————————————————————————
  document.addEventListener('DOMContentLoaded', () => {

    // Bouton "Actualiser la page" (vide / pas de circuits)
    document.querySelectorAll('[data-refresh="true"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const clean = new URL(window.location.href);
        // on supprime tous les paramètres (q, from, sort, page, etc.)
        clean.search = '';
        clean.hash = 'circuits';
        window.location.assign(clean.toString());
      });
    });



    // Machine à écrire
    const typewriterElement = document.querySelector('.typewriter-text');
    if (typewriterElement) new TypeWriter(typewriterElement);

    // Particules titre
    const titleContainer = document.querySelector('.typewriter-container');
    if (titleContainer) {
      titleContainer.style.position = 'relative';
      titleContainer.style.display = 'inline-block';
      new TitleParticles(titleContainer);
    }

    // Effet tilt global
    initTiltEffect();

    // Circuit list (évite double init)
    const container = document.querySelector('[data-controller="circuit-list"]');
    if (container && !container.__circuitListInstance) {
      container.__circuitListInstance = new CircuitList(container);
    }

    // Formulaire « Déjà inscrit »
    const editForm = document.querySelector('[data-edit-form="true"]');
    if (editForm) {
      editForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const refInput = document.querySelector('[data-uuid-input="true"]');
        const ref = (refInput?.value || '').trim();
        if (isValidUUID(ref)) {
          window.location.href = `/inscription/${ref}/modifier/`;
        } else {
          showNotification(gettext('Référence invalide. Veuillez vérifier votre UUID.'), 'error');
        }
      });
    }

    // QuickViewPremium — observer unique
    const modalBody = document.querySelector('[data-modal-body="true"]');
    if (modalBody && !modalBody.__qvObserverAttached) {
      const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
          if (m.type === 'childList' && m.addedNodes.length) {
            const qv = modalBody.querySelector('.qv-premium');
            if (qv && !modalBody.__qvInitRun) {
              new window.QuickViewPremium(modalBody);
              modalBody.__qvInitRun = true;
            }
          }
        }
      });
      observer.observe(modalBody, { childList: true, subtree: true });
      modalBody.__qvObserverAttached = true;
    }
  });

  // ——————————————————————————————————————
  // Reflow des particules sur resize
  // ——————————————————————————————————————
  window.addEventListener('resize', () => {
    const particles = document.querySelectorAll('.title-particle');
    particles.forEach(p => p.remove());
    const titleContainer = document.querySelector('.typewriter-container');
    if (titleContainer) new TitleParticles(titleContainer);
  });


  // ——————————————————————————————————————
  // Filtres serveur (GET) : synchro formulaire <-> URL, pagination
  // ——————————————————————————————————————
  function _paramsFromForm(form) {
    const fd = new FormData(form);
    const params = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      if (String(v || '').trim() !== '') params.set(k, v);
    }
    return params;
  }

  function _applyURLToForm(form) {
    const urlParams = new URLSearchParams(window.location.search);
    ['q', 'from', 'sort'].forEach((name) => {
      const el = form.querySelector(`[name="${name}"]`);
      if (el && urlParams.has(name)) el.value = urlParams.get(name);
    });
  }

  function _submitFilters(form) {
    const url = new URL(window.location.href);
    const params = _paramsFromForm(form);
    // Toujours repartir à la page 1 quand on change un filtre
    params.delete('page');
    url.search = params.toString();
    url.hash = 'circuits';
    window.location.assign(url.toString());
  }

  function _decoratePaginationLinks(form) {
    const nav = document.querySelector('[data-pagination="true"][data-keep-filters="true"]');
    if (!nav) return;
    const baseParams = _paramsFromForm(form);
    baseParams.delete('page');

    nav.querySelectorAll('a.page-link').forEach((a) => {
      try {
        const u = new URL(a.getAttribute('href'), window.location.href);
        // Injecte tous les filtres courants dans les liens de pagination
        for (const [k, v] of baseParams.entries()) u.searchParams.set(k, v);
        u.hash = 'circuits';
        a.setAttribute('href', u.pathname + '?' + u.searchParams.toString() + u.hash);
      } catch (e) { /* lien relatif — on ignore */ }
    });
  }

  // Boot “filtres serveur”
  document.addEventListener('DOMContentLoaded', () => {


    // Bouton "Actualiser la page" (vide / pas de circuits)
    document.querySelectorAll('[data-refresh="true"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const clean = new URL(window.location.href);
        // on supprime tous les paramètres (q, from, sort, page, etc.)
        clean.search = '';
        clean.hash = 'circuits';
        window.location.assign(clean.toString());
      });
    });


    const form = document.getElementById('filters');
    if (!form || form.dataset.server !== 'true') return;

    // 1) Remplir les champs depuis l’URL (back + front alignés)
    _applyURLToForm(form);

    // 2) Autosoumission raffinée (serveur)
    const qInput    = form.querySelector('input[name="q"]');
    const fromInput = form.querySelector('input[name="from"]');
    const sortSel   = form.querySelector('select[name="sort"]');

    // Recherche : Enter immédiat + debounce sur pause de frappe
    if (qInput) {
      let tId;
      qInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); _submitFilters(form); }
      });
      qInput.addEventListener('input', () => {
        clearTimeout(tId);
        const val = (qInput.value || '').trim();
        // si rien → on envoie vite pour enlever le filtre
        if (val.length === 0) {
          tId = setTimeout(() => _submitFilters(form), 300);
          return;
        }
        // éviter de spammer pour 1 seul caractère
        if (val.length < 2) return;
        tId = setTimeout(() => _submitFilters(form), 700);
      });
    }

    // Date & tri : uniquement au change
    fromInput?.addEventListener('change', () => _submitFilters(form));
    sortSel?.addEventListener('change',  () => _submitFilters(form));

    // Form submit (si on appuie sur Enter ailleurs)
    form.addEventListener('submit', (e) => { e.preventDefault(); _submitFilters(form); });


    // 4) Réécrire la pagination pour conserver les filtres actifs
    _decoratePaginationLinks(form);
  });



})();

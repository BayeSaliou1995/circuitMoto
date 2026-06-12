// static/circuitMoto/js/circuit_detail.js

(function () {
  "use strict";

  document.documentElement.classList.add("js");


  const CONFIG = {
    magneticStrength: 0.3,
    aosDuration: 600,
    particles: 16,
    carouselSpeed: 3500
  };

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function showNotification(message, type = "info") {
    const n = document.createElement("div");
    n.className = "notification";
    const icon = type === "success" ? "check-circle" : type === "error" ? "triangle-exclamation" : "info-circle";

    n.innerHTML = `
      <div class="notification-content ${type}" role="status" aria-live="polite">
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
      </div>
    `;

    document.body.appendChild(n);

    const ttl = 2400;
    setTimeout(() => {
      n.style.opacity = "0";
      n.style.transform = "translateX(10px)";
      setTimeout(() => n.remove(), 260);
    }, ttl);
  }

  // Fonctions globales (car tu as des onclick="" dans le template)
  window.scrollToSection = function (id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  window.shareCircuit = function () {
    const modal = $("#shareModal");
    if (!modal) return;
    modal.classList.add("show");
    modal.style.display = "flex";
  };

  window.closeModal = function () {
    const modal = $("#shareModal");
    if (!modal) return;
    modal.classList.remove("show");
    setTimeout(() => (modal.style.display = "none"), 250);
  };

  function copyToClipboardFallback(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      return true;
    } catch (e) {
      return false;
    } finally {
      ta.remove();
    }
  }

  window.copyShareLink = function () {
    const url = window.location.href;
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard
        .writeText(url)
        .then(() => {
          showNotification("Lien copié dans le presse-papier !", "success");
          window.closeModal();
        })
        .catch(() => {
          const ok = copyToClipboardFallback(url);
          if (ok) {
            showNotification("Lien copié !", "success");
            window.closeModal();
          } else {
            showNotification("Impossible de copier le lien.", "error");
          }
        });
    } else {
      const ok = copyToClipboardFallback(url);
      if (ok) {
        showNotification("Lien copié !", "success");
        window.closeModal();
      } else {
        showNotification("Impossible de copier le lien.", "error");
      }
    }
  };

  window.shareSocial = function (platform) {
    const url = encodeURIComponent(window.location.href);
    const title = encodeURIComponent(document.title);
    const socialUrls = {
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${url}`,
      twitter: `https://twitter.com/intent/tweet?text=${title}&url=${url}`,
      linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`
    };
    if (!socialUrls[platform]) return;
    window.open(socialUrls[platform], "_blank", "width=600,height=420");
  };

  const escapeHTML = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    }[ch]));

  function loadGoogleMapsApi(key) {
    if (window.google && window.google.maps) return Promise.resolve();
    if (!key) return Promise.reject(new Error("missing-google-maps-key"));
    if (window.__pulsionGoogleMapsPromise) return window.__pulsionGoogleMapsPromise;

    window.__pulsionGoogleMapsPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly`;
      script.async = true;
      script.defer = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("google-maps-load-failed"));
      document.head.appendChild(script);
    });

    return window.__pulsionGoogleMapsPromise;
  }

  function initRouteExplorer() {
    const root = document.querySelector("[data-route-explorer]");
    const dataNode = document.getElementById("circuitRouteData");
    if (!root || !dataNode) return;

    let data = {};
    try {
      data = JSON.parse(dataNode.textContent || "{}");
    } catch (e) {
      data = {};
    }

    const days = Array.isArray(data.days) ? data.days : [];
    const flatPoints = [];
    days.forEach((day, dayIndex) => {
      (Array.isArray(day.points) ? day.points : []).forEach((point) => {
        if (Number.isFinite(point.lat) && Number.isFinite(point.lng)) {
          flatPoints.push({ ...point, dayIndex });
        }
      });
    });

    const els = {
      map: root.querySelector("[data-route-map]"),
      street: root.querySelector("[data-route-street]"),
      fallback: root.querySelector("[data-route-fallback]"),
      days: root.querySelector("[data-route-days]"),
      day: root.querySelector("[data-route-day]"),
      title: root.querySelector("[data-route-title]"),
      meta: root.querySelector("[data-route-meta]"),
      prev: root.querySelector("[data-route-prev]"),
      next: root.querySelector("[data-route-next]"),
      reset: root.querySelector("[data-route-reset]"),
      fullscreen: root.querySelector("[data-route-fullscreen]")
    };

    if (!els.map) return;

    const key = (root.dataset.googleKey || "").trim();
    let map = null;
    let panorama = null;
    let overviewPath = null;
    let activePath = null;
    let markers = [];
    let currentIndex = 0;
    let mapReady = false;
    let vectorActiveIndex = null;

    const googlePoint = (point) => ({ lat: point.lat, lng: point.lng });

    function setPanel(day) {
      if (!els.day || !els.title || !els.meta) return;

      if (!day) {
        els.day.textContent = "Jour par jour";
        els.title.textContent = data.title || "";
        els.meta.textContent = flatPoints.length ? `${flatPoints.length} étapes` : "";
        return;
      }

      els.day.textContent = day.day || `Jour ${currentIndex + 1}`;
      els.title.textContent = day.title || data.title || "";
      els.meta.textContent = [day.distance, day.duration].filter(Boolean).join(" · ");
    }

    function setButtonsActive(selector, attr, value) {
      root.querySelectorAll(selector).forEach((btn) => {
        const active = btn.dataset[attr] === value;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function renderDayButtons() {
      if (!els.days) return;
      els.days.innerHTML = "";
      if (!days.length) {
        els.days.hidden = true;
        return;
      }
      els.days.hidden = false;

      days.forEach((day, index) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "route-day-chip";
        btn.dataset.routeDay = String(index);
        btn.setAttribute("role", "tab");
        btn.innerHTML = `
          <span>${escapeHTML(day.day || `Jour ${index + 1}`)}</span>
          <strong>${escapeHTML(day.title || "")}</strong>
        `;
        btn.addEventListener("click", () => setDay(index));
        els.days.appendChild(btn);
      });
    }

    function updateDayButtons() {
      if (!els.days) return;
      els.days.querySelectorAll("[data-route-day]").forEach((btn) => {
        const active = Number(btn.dataset.routeDay) === currentIndex;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      });
    }

    function fitPoints(points) {
      if (!map || !points.length || !window.google) return;
      const bounds = new google.maps.LatLngBounds();
      points.forEach((point) => bounds.extend(googlePoint(point)));
      map.fitBounds(bounds, 58);
      if (points.length === 1) map.setZoom(Math.min(map.getZoom() || 11, 11));
    }

    function fitOverview() {
      vectorActiveIndex = null;
      setPanel(null);
      if (mapReady && flatPoints.length) {
        fitPoints(flatPoints);
        if (activePath) activePath.setPath([]);
        markers.forEach((marker) => marker.setOpacity(1));
      } else {
        renderVectorMap(null);
      }
    }

    function setMapType(type) {
      setButtonsActive("[data-route-map-type]", "routeMapType", type);
      if (map) map.setMapTypeId(type === "satellite" ? "satellite" : "roadmap");
    }

    function setView(view) {
      const isStreet = view === "street";
      setButtonsActive("[data-route-view]", "routeView", isStreet ? "street" : "map");
      root.classList.toggle("is-street-view", isStreet);
      if (els.map) els.map.hidden = isStreet;
      if (els.street) els.street.hidden = !isStreet;
      if (els.fallback) els.fallback.hidden = true;

      if (isStreet && !mapReady) renderStreetFallback();
      if (!isStreet && !mapReady) renderVectorMap(vectorActiveIndex);
    }

    function renderIframe(target, src, title) {
      target.innerHTML = `
        <iframe
          title="${escapeHTML(title)}"
          src="${escapeHTML(src)}"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"
          allowfullscreen>
        </iframe>
      `;
    }

    function renderStreetFallback() {
      if (!els.street) return;
      if (data.streetViewUrl) {
        renderIframe(els.street, data.streetViewUrl, "Street View");
        return;
      }

      const day = days[currentIndex];
      const link = day?.mapsUrl || data.mapsUrl || "";
      els.street.innerHTML = `
        <div class="route-empty-state">
          <i class="fas fa-street-view" aria-hidden="true"></i>
          <strong>Street View</strong>
          ${link ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener">Ouvrir dans Google Maps</a>` : ""}
        </div>
      `;
    }

    function renderVectorMap(activeIndex) {
      vectorActiveIndex = activeIndex;
      if (!els.map) return;

      if (!flatPoints.length && data.embedUrl) {
        renderIframe(els.map, data.embedUrl, "Google Maps");
        return;
      }

      if (!flatPoints.length) {
        els.map.innerHTML = `
          <div class="route-empty-state">
            <i class="fas fa-map-location-dot" aria-hidden="true"></i>
            <strong>Carte à configurer</strong>
          </div>
        `;
        return;
      }

      const lats = flatPoints.map((p) => p.lat);
      const lngs = flatPoints.map((p) => p.lng);
      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLng = Math.min(...lngs);
      let maxLng = Math.max(...lngs);
      if (minLat === maxLat) {
        minLat -= 0.5;
        maxLat += 0.5;
      }
      if (minLng === maxLng) {
        minLng -= 0.5;
        maxLng += 0.5;
      }

      const project = (point) => {
        const x = 64 + ((point.lng - minLng) / (maxLng - minLng)) * 872;
        const y = 456 - ((point.lat - minLat) / (maxLat - minLat)) * 392;
        return { x, y };
      };

      const path = flatPoints.map(project).map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
      const activePoints = activeIndex === null ? [] : flatPoints.filter((p) => p.dayIndex === activeIndex);
      const activePath = activePoints.map(project).map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
      const markersSvg = flatPoints.map((point, index) => {
        const p = project(point);
        const active = activeIndex === null || point.dayIndex === activeIndex;
        return `
          <g class="${active ? "is-active" : ""}">
            <circle cx="${p.x}" cy="${p.y}" r="${active ? 13 : 9}"></circle>
            <text x="${p.x}" y="${p.y + 4}">${index + 1}</text>
          </g>
        `;
      }).join("");

      els.map.innerHTML = `
        <div class="route-vector-map">
          <svg viewBox="0 0 1000 520" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
            <defs>
              <pattern id="routeGrid" width="64" height="64" patternUnits="userSpaceOnUse">
                <path d="M64 0H0V64" fill="none" stroke="rgba(15,23,42,.08)" stroke-width="1"/>
              </pattern>
            </defs>
            <rect width="1000" height="520" fill="url(#routeGrid)"></rect>
            <polyline points="${path}" fill="none" class="route-vector-line"></polyline>
            ${activePath ? `<polyline points="${activePath}" fill="none" class="route-vector-line route-vector-line-active"></polyline>` : ""}
            <g class="route-vector-markers">${markersSvg}</g>
          </svg>
        </div>
      `;
    }

    function setDay(index) {
      if (!days.length) {
        fitOverview();
        return;
      }

      currentIndex = (index + days.length) % days.length;
      const day = days[currentIndex];
      const dayPoints = Array.isArray(day.points) ? day.points : [];
      setPanel(day);
      updateDayButtons();

      if (mapReady) {
        if (activePath) activePath.setPath(dayPoints.map(googlePoint));
        if (dayPoints.length) fitPoints(dayPoints);
        markers.forEach((marker) => marker.setOpacity(marker.__dayIndex === currentIndex ? 1 : 0.36));

        if (panorama && day.streetView) {
          panorama.setPosition({ lat: day.streetView.lat, lng: day.streetView.lng });
          panorama.setPov({
            heading: day.streetView.heading || 0,
            pitch: day.streetView.pitch || 0
          });
          panorama.setZoom(day.streetView.zoom || 1);
        }
      } else {
        renderVectorMap(currentIndex);
        renderStreetFallback();
      }
    }

    function initGoogleMap() {
      if (!flatPoints.length) {
        renderVectorMap(null);
        return;
      }

      const center = data.center || flatPoints[0] || { lat: 48.8566, lng: 2.3522 };
      map = new google.maps.Map(els.map, {
        center: googlePoint(center),
        zoom: 4,
        mapTypeId: "roadmap",
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        gestureHandling: "greedy"
      });

      overviewPath = new google.maps.Polyline({
        path: flatPoints.map(googlePoint),
        map,
        strokeColor: "#dc2626",
        strokeOpacity: 0.92,
        strokeWeight: 4
      });

      activePath = new google.maps.Polyline({
        path: [],
        map,
        strokeColor: "#111827",
        strokeOpacity: 0.9,
        strokeWeight: 6
      });

      markers = flatPoints.map((point, index) => {
        const marker = new google.maps.Marker({
          position: googlePoint(point),
          map,
          title: point.label || "",
          label: { text: String(index + 1), color: "#fff", fontWeight: "800" },
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 10,
            fillColor: "#2563eb",
            fillOpacity: 1,
            strokeColor: "#ffffff",
            strokeWeight: 3
          }
        });
        marker.__dayIndex = point.dayIndex;
        return marker;
      });

      if (els.street) {
        const firstStreet = days.find((day) => day.streetView)?.streetView || flatPoints[0];
        panorama = new google.maps.StreetViewPanorama(els.street, {
          position: googlePoint(firstStreet),
          pov: {
            heading: firstStreet.heading || 0,
            pitch: firstStreet.pitch || 0
          },
          zoom: firstStreet.zoom || 1,
          addressControl: true,
          fullscreenControl: false,
          motionTracking: false
        });
      }

      mapReady = true;
      fitOverview();
      if (days.length) setDay(0);
    }

    renderDayButtons();
    setPanel(null);
    renderVectorMap(null);

    root.querySelectorAll("[data-route-map-type]").forEach((btn) => {
      btn.addEventListener("click", () => setMapType(btn.dataset.routeMapType || "roadmap"));
    });

    root.querySelectorAll("[data-route-view]").forEach((btn) => {
      btn.addEventListener("click", () => setView(btn.dataset.routeView || "map"));
    });

    if (els.prev) els.prev.addEventListener("click", () => setDay(currentIndex - 1));
    if (els.next) els.next.addEventListener("click", () => setDay(currentIndex + 1));
    if (els.reset) els.reset.addEventListener("click", fitOverview);
    if (els.fullscreen) {
      els.fullscreen.addEventListener("click", () => {
        const target = root.querySelector(".route-viewport") || root;
        if (target.requestFullscreen) target.requestFullscreen();
      });
    }

    loadGoogleMapsApi(key)
      .then(initGoogleMap)
      .catch(() => {
        root.classList.add("is-fallback");
        renderVectorMap(null);
        if (days.length) setDay(0);
      });
  }

  class CircuitAnimator {
    init() {
      this.root = $("#circuitDetail");
      if (!this.root) return;

      this.initMagnetic();
      this.initAOS();
      this.initParallax();
      this.initParticles();
      this.initNavState();
      this.initProgressBar();
      this.initCounters();
      this.initCarousel();
      this.initModal();

      // ✅ on récupère le banner (ou null) puis on lance le typewriter
      this.initNBanner();        // garde ta logique sessionStorage + close
      this.initNBTypewriter();   // ✅ typewriter autonome


      this.fixHashOnLoad();
      this.renumberRoadbook();
      this.setViewportUnit();

      this.initHeroCollapsibles();
      this.initHeroTitleTypewriter();
      initRouteExplorer();

      this.initFooterInView();


    }

    initMagnetic() {
      if (reduceMotion) return;

      $$(".magnetic").forEach((el) => {
        let raf = null;
        const strength = parseFloat(el.dataset.strength) || CONFIG.magneticStrength;

        const onMove = (e) => {
          const r = el.getBoundingClientRect();
          const x = e.clientX - r.left - r.width / 2;
          const y = e.clientY - r.top - r.height / 2;

          if (raf) cancelAnimationFrame(raf);
          raf = requestAnimationFrame(() => {
            el.style.setProperty("--mag-x", `${x * strength}px`);
            el.style.setProperty("--mag-y", `${y * strength}px`);
          });
        };

        const onLeave = () => {
          if (raf) cancelAnimationFrame(raf);
          el.style.setProperty("--mag-x", "0px");
          el.style.setProperty("--mag-y", "0px");
        };

        el.addEventListener("mousemove", onMove, { passive: true });
        el.addEventListener("mouseleave", onLeave, { passive: true });
      });
    }

    initAOS() {
      const elements = $$("[data-aos]");
      if (!elements.length) return;

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;

            const el = entry.target;
            const anim = el.dataset.aos || "fade-up";
            const delay = parseInt(el.dataset.aosDelay, 10) || 0;

            setTimeout(() => {
              el.style.animation = `${anim} ${CONFIG.aosDuration}ms ease-out forwards`;
            }, delay);

            observer.unobserve(el);
          });
        },
        { threshold: 0.12 }
      );

      elements.forEach((el) => observer.observe(el));
    }

    initParallax() {
      if (reduceMotion) return;

      const elements = $$("[data-speed]");
      if (!elements.length) return;

      let ticking = false;
      const update = () => {
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        elements.forEach((el) => {
          const speed = parseFloat(el.dataset.speed) || 0;
          el.style.transform = `translateY(${-(y * speed)}px)`;
        });
        ticking = false;
      };

      const onScroll = () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(update);
      };

      window.addEventListener("scroll", onScroll, { passive: true });
      update();
    }

    initParticles() {
      if (reduceMotion) return;

      const container = $("#heroParticles");
      if (!container) return;

      for (let i = 0; i < CONFIG.particles; i++) {
        const p = document.createElement("div");
        p.className = "particle";

        const size = Math.random() * 18 + 6;
        const posX = Math.random() * 100;
        const posY = Math.random() * 100;
        const duration = Math.random() * 10 + 12;

        p.style.width = `${size}px`;
        p.style.height = `${size}px`;
        p.style.left = `${posX}%`;
        p.style.top = `${posY}%`;
        p.style.animation = `float ${duration}s ease-in-out ${Math.random() * 2}s infinite`;

        container.appendChild(p);
      }
    }

    initNavState() {
      const nav = $("#detailNav");
      const hero = $("#heroSection");
      if (!nav || !hero) return;

      const navHeight =
        parseInt(getComputedStyle(document.documentElement).getPropertyValue("--nav-height"), 10) || 70;

      const heroObserver = new IntersectionObserver(
        ([entry]) => {
          const inHero = entry.isIntersecting;
          nav.classList.toggle("is-scrolled", !inHero);
          nav.dataset.phase = inHero ? "hero" : "content";
        },
        { rootMargin: `-${navHeight}px 0px 0px 0px`, threshold: 0.01 }
      );
      heroObserver.observe(hero);

      const navLinks = $$(".detail-nav .nav-link");
      const sections = $$(".content-section").filter((s) =>
        navLinks.some((l) => l.getAttribute("href") === `#${s.id}`)
      );

      const sectionObserver = new IntersectionObserver(
        (entries) => {
          let best = null;
          let bestRatio = 0;

          entries.forEach((e) => {
            if (e.intersectionRatio > bestRatio) {
              bestRatio = e.intersectionRatio;
              best = e.target;
            }
          });

          if (best && bestRatio > 0.01) {
            navLinks.forEach((l) => {
              l.classList.remove("active");
              l.removeAttribute("aria-current");
            });

            const active = navLinks.find((l) => l.getAttribute("href") === `#${best.id}`);
            if (active) {
              active.classList.add("active");
              active.setAttribute("aria-current", "page");
              this.scrollNavToVisible(active);
            }
          }
        },
        { rootMargin: "-20% 0px -58% 0px", threshold: [0.01, 0.25, 0.5, 0.75] }
      );

      sections.forEach((s) => sectionObserver.observe(s));

      navLinks.forEach((link) => {
        link.addEventListener("click", (e) => {
          e.preventDefault();
          const href = link.getAttribute("href");
          const target = href ? document.querySelector(href) : null;
          if (!target) return;

          target.scrollIntoView({ behavior: "smooth", block: "start" });

          navLinks.forEach((l) => {
            l.classList.remove("active");
            l.removeAttribute("aria-current");
          });
          link.classList.add("active");
          link.setAttribute("aria-current", "page");
          this.scrollNavToVisible(link);
        });
      });
    }

    scrollNavToVisible(link) {
      const navScroll = $(".nav-scroll");
      if (!navScroll || !link) return;

      const s = navScroll.getBoundingClientRect();
      const l = link.getBoundingClientRect();
      const pad = 16;

      if (l.left < s.left) {
        navScroll.scrollBy({ left: l.left - s.left - pad, behavior: "smooth" });
      } else if (l.right > s.right) {
        navScroll.scrollBy({ left: l.right - s.right + pad, behavior: "smooth" });
      }
    }

    initProgressBar() {
      const nav = $("#detailNav");
      if (!nav) return;
      const bar = nav.querySelector(".scroll-progress");
      if (!bar) return;

      let ticking = false;
      const update = () => {
        const docH = Math.max(
          document.body.scrollHeight,
          document.documentElement.scrollHeight,
          document.body.offsetHeight,
          document.documentElement.offsetHeight
        );
        const winH = window.innerHeight;
        const top = window.scrollY || document.documentElement.scrollTop;
        const pct = (top / (docH - winH)) || 0;
        bar.style.transform = `scaleX(${Math.min(pct, 1)})`;
        ticking = false;
      };

      window.addEventListener(
        "scroll",
        () => {
          if (ticking) return;
          ticking = true;
          requestAnimationFrame(update);
        },
        { passive: true }
      );

      update();
    }

    initCounters() {
      const counters = $$("[data-counter]");
      if (!counters.length) return;

      const animate = (el, target) => {
        const duration = 900;
        const start = performance.now();

        const tick = (now) => {
          const p = Math.min((now - start) / duration, 1);
          el.textContent = String(Math.floor(p * target));
          if (p < 1) requestAnimationFrame(tick);
          else el.textContent = String(target);
        };
        requestAnimationFrame(tick);
      };

      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            if (!e.isIntersecting) return;
            const t = parseInt(e.target.dataset.counter, 10) || 0;
            animate(e.target, t);
            obs.unobserve(e.target);
          });
        },
        { threshold: 0.55 }
      );

      counters.forEach((c) => obs.observe(c));
    }

    initCarousel() {
      const track = $("#circuitsCarouselTrack");
      if (!track) return;

      const baseCards = $$(".circuit-card", track);
      if (!baseCards.length) return;

      const original = [...baseCards];
      const minCards = Math.max(baseCards.length * 2, 8);

      while (track.children.length < minCards) {
        original.forEach((c) => track.appendChild(c.cloneNode(true)));
      }

      const all = $$(".circuit-card", track);
      let index = 0;
      let paused = false;
      let timer = null;

      const measure = () => {
        const first = all[0];
        if (!first) return { step: 0, visible: 1 };

        const trackStyle = getComputedStyle(track);
        const gap = parseFloat(trackStyle.gap) || parseFloat(trackStyle.columnGap) || 24;
        const w = first.getBoundingClientRect().width;

        const container = track.parentElement;
        const visible = Math.max(1, Math.floor(container.getBoundingClientRect().width / (w + gap)));

        return { step: Math.round(w + gap), visible };
      };

      const next = () => {
        if (paused) return;

        const m = measure();
        if (!m.step) return;

        index++;
        track.style.transition = "transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)";
        track.style.transform = `translateX(-${index * m.step}px)`;

        const maxIndex = all.length - m.visible;
        if (index >= maxIndex) {
          setTimeout(() => {
            track.style.transition = "none";
            index = 0;
            track.style.transform = "translateX(0)";
          }, 820);
        }
      };

      const start = () => {
        stop();
        timer = setInterval(next, CONFIG.carouselSpeed);
      };

      const stop = () => {
        if (!timer) return;
        clearInterval(timer);
        timer = null;
      };

      const container = track.parentElement;
      const pause = () => (paused = true);
      const resume = () => (paused = false);

      ["mouseenter", "focusin", "touchstart"].forEach((evt) => container.addEventListener(evt, pause, { passive: true }));
      ["mouseleave", "focusout", "touchend"].forEach((evt) => container.addEventListener(evt, resume, { passive: true }));

      start();

      window.addEventListener(
        "resize",
        () => {
          // recalcul implicite au prochain tick
        },
        { passive: true }
      );
    }

    initModal() {
      const modal = $("#shareModal");
      if (!modal) return;

      modal.addEventListener("click", (e) => {
        if (e.target === modal) window.closeModal();
      });

      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal.classList.contains("show")) window.closeModal();
      });
    }

    initNBanner() {
    const banner = $("#nbBanner");
    if (!banner) return null;

    try {
        if (sessionStorage.getItem("nbBannerClosed") === "true") {
        banner.remove();
        return null;
        }
    } catch (e) {}

    const btn = banner.querySelector(".nb-close");
    if (btn && btn.dataset.bound !== "1") {
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {
        banner.style.opacity = "0";
        banner.style.transform = "translateY(-10px)";
        setTimeout(() => {
            banner.remove();
            try { sessionStorage.setItem("nbBannerClosed", "true"); } catch (e) {}
        }, 260);
        });
    }

    return banner; // ✅ IMPORTANT
    }


    initNBTypewriter() {
      const p = document.querySelector("#nbBanner .nb-text[data-nb-typewriter]");
      if (!p) return;
      if (p.dataset.twInit === "1") return;
      p.dataset.twInit = "1";

      const full = (p.textContent || "").replace(/\s+/g, " ").trim();
      if (!full) return;

      if (reduceMotion) {
        p.textContent = full;
        return;
      }

      // Réglages (lent & lisible)
      const speed = parseInt(p.dataset.twSpeed, 10) || 26;       // ms/char
      const startDelay = parseInt(p.dataset.twStart, 10) || 260; // ms
      const jitter = parseInt(p.dataset.twJitter, 10) || 12;     // ms

      // Structure accessible
      p.classList.add("tw-para");

      const sr = document.createElement("span");
      sr.className = "tw-sr";
      sr.textContent = full;

      const text = document.createElement("span");
      text.className = "tw-text";
      text.setAttribute("aria-hidden", "true");
      text.textContent = "";

      const caret = document.createElement("span");
      caret.className = "tw-caret";
      caret.setAttribute("aria-hidden", "true");
      caret.textContent = "▍";

      p.textContent = "";
      p.append(sr, text, caret);

      let i = 0;
      let timer = null;
      let started = false;

      const clearTimer = () => {
        if (timer) clearTimeout(timer);
        timer = null;
      };

      const nextDelay = (ch) => {
        let extra = 0;
        if (/[.!?]/.test(ch)) extra = 240;
        else if (/[,;:]/.test(ch)) extra = 140;
        else if (ch === " ") extra = 35;
        return speed + Math.random() * jitter + extra;
      };

      const step = () => {
        i++;
        text.textContent = full.slice(0, i);

        if (i >= full.length) {
          clearTimer();
          setTimeout(() => { caret.style.opacity = "0"; }, 900);
          return;
        }
        const ch = full[i - 1];
        clearTimer();
        timer = setTimeout(step, nextDelay(ch));
      };

      const start = () => {
        if (started) return;
        started = true;
        clearTimer();
        timer = setTimeout(step, startDelay);
      };

      const isInViewNow = () => {
        const r = p.getBoundingClientRect();
        return r.top < window.innerHeight * 0.92 && r.bottom > 0;
      };

      // ✅ Start si déjà visible
      if (isInViewNow()) {
        requestAnimationFrame(start);
      }
      // ✅ Sinon IO
      else if ("IntersectionObserver" in window) {
        const io = new IntersectionObserver((entries) => {
          if (entries[0]?.isIntersecting) {
            start();
            io.disconnect();
          }
        }, { threshold: 0.15, rootMargin: "0px 0px -10% 0px" });
        io.observe(p);
      }

      // ✅ Fallback SI IO ne déclenche pas (ultra important)
      setTimeout(() => {
        if (!started) start();
      }, 800);

      // Tap/clic = afficher tout
      p.addEventListener("pointerdown", () => {
        clearTimer();
        text.textContent = full;
        caret.style.opacity = "0";
      }, { passive: true, once: true });
    }



    fixHashOnLoad() {
      const hash = window.location.hash;
      if (!hash || hash.length <= 1) return;

      const el = document.querySelector(hash);
      if (!el) return;

      setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 140);
    }

    renumberRoadbook() {
      const days = $$("#programme .timeline-day");
      days.forEach((dayEl, idx) => {
        const title = (dayEl.querySelector(".day-header h3")?.textContent || "").trim();
        const bubble = dayEl.querySelector(".day-number");
        const badge = dayEl.querySelector(".day-badge");

        const match = /^\s*Jour\s+(\d+[A-Za-z]{0,2})\b/i.exec(title);
        if (match) {
          const n = match[1].toUpperCase();
          if (bubble) bubble.textContent = `J${n}`;
          if (badge) badge.textContent = `Jour ${n}`;
        } else {
          if (bubble) bubble.textContent = `J${idx + 1}`;
          if (badge) badge.textContent = `Jour ${idx + 1}`;
        }
      });
    }

    setViewportUnit() {
      const setVH = () => {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty("--vh", `${vh}px`);
      };
      window.addEventListener("resize", setVH, { passive: true });
      setVH();
    }

    initHeroCollapsibles() {
    const boxes = $$(".meta-collapsible[data-collapsible]");
    if (!boxes.length) return;

    const mq = window.matchMedia("(max-width: 640px)");

    const setLabel = (btn, txt) => {
        const s = btn.querySelector(".label");
        if (s) s.textContent = txt;
        else btn.textContent = txt;
    };

    const getCollapsedH = (box) => {
        const v = parseInt(box.dataset.collapsedHeight, 10);
        return Number.isFinite(v) ? v : 120;
    };

    const getLabels = (box) => ({
        closed: box.dataset.closedLabel || "Voir tout",
        open: box.dataset.openLabel || "Afficher moins",
    });

    const needsToggle = (box, collapsedH) => box.scrollHeight > collapsedH + 8;

    const applyOne = (box) => {
        if (!box.id) box.id = `coll_${Math.random().toString(36).slice(2, 9)}`;

        const btn = document.querySelector(
        `[data-collapsible-toggle][aria-controls="${box.id}"]`
        );
        if (!btn) return;

        const collapsedH = getCollapsedH(box);
        const { closed, open } = getLabels(box);

        const enableMobile = mq.matches;
        const need = enableMobile && needsToggle(box, collapsedH);

        // Bind click once
        if (btn.dataset.bound !== "1") {
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {
            if (!mq.matches) return;

            const isOpen = box.classList.contains("is-open");

            if (isOpen) {
            // COLLAPSE
            box.dataset.userOpen = "0";
            const current = box.getBoundingClientRect().height;
            box.style.maxHeight = `${current}px`;
            box.offsetHeight; // force reflow

            box.classList.remove("is-open");
            box.classList.add("is-collapsed");
            box.style.maxHeight = `${collapsedH}px`;

            btn.setAttribute("aria-expanded", "false");
            setLabel(btn, closed);
            } else {
            // EXPAND
            box.dataset.userOpen = "1";
            box.classList.add("is-open");
            box.classList.remove("is-collapsed");

            const h = box.scrollHeight;
            box.style.maxHeight = `${h}px`;

            btn.setAttribute("aria-expanded", "true");
            setLabel(btn, open);

            const onEnd = (e) => {
                if (e.propertyName !== "max-height") return;
                if (box.classList.contains("is-open")) box.style.maxHeight = "none";
                box.removeEventListener("transitionend", onEnd);
            };
            box.addEventListener("transitionend", onEnd);
            }
        });
        }

        // Desktop ou texte court → tout afficher, bouton caché
        if (!need) {
        btn.hidden = true;
        btn.setAttribute("aria-expanded", "true");
        box.classList.remove("is-collapsed", "is-open");
        box.style.maxHeight = "none";
        return;
        }

        // Mobile + texte long → activer toggle
        btn.hidden = false;

        const userOpen = box.dataset.userOpen === "1";
        if (userOpen) {
        box.classList.add("is-open");
        box.classList.remove("is-collapsed");
        box.style.maxHeight = "none";
        btn.setAttribute("aria-expanded", "true");
        setLabel(btn, open);
        } else {
        box.classList.remove("is-open");
        box.classList.add("is-collapsed");
        box.style.maxHeight = `${collapsedH}px`;
        btn.setAttribute("aria-expanded", "false");
        setLabel(btn, closed);
        }
    };

    const applyAll = () => boxes.forEach(applyOne);

    // Après chargement des polices (meilleure mesure)
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => applyAll()).catch(() => {});
    }

    applyAll();

    // Resize: recalcul simple
    let raf = null;
    window.addEventListener(
        "resize",
        () => {
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(applyAll);
        },
        { passive: true }
    );

    // Breakpoint change
    if (mq.addEventListener) mq.addEventListener("change", applyAll);
    else mq.addListener(applyAll);
    }

initHeroTitleTypewriter() {
  const title = $("#circuitTitle");
  if (!title) return;
  if (title.dataset.twInit === "1") return;
  title.dataset.twInit = "1";

  const full = (title.textContent || "").replace(/\s+/g, " ").trim();
  if (!full) return;

  if (reduceMotion) {
    title.textContent = full;
    return;
  }

  // boucle activée par défaut sauf si data-tw-loop="0"
  const loop = title.dataset.twLoop !== "0";

  const speed = parseInt(title.dataset.twSpeed, 10) || 32;
  const startDelay = parseInt(title.dataset.twStart, 10) || 180;
  const jitter = parseInt(title.dataset.twJitter, 10) || 18;
  const hold = parseInt(title.dataset.twHold, 10) || 1100;
  const holdEmpty = parseInt(title.dataset.twHoldEmpty, 10) || 450;
  const backSpeed = parseInt(title.dataset.twBackSpeed, 10) || 18;
  const backJitter = parseInt(title.dataset.twBackJitter, 10) || 10;

  title.classList.add("tw-gradient");
  if (loop) title.classList.add("tw-loop");

  // Accessibilité
  const sr = document.createElement("span");
  sr.className = "tw-sr";
  sr.textContent = full;

  // Ghost = réserve la place finale du titre
  const ghost = document.createElement("span");
  ghost.className = "tw-ghost";
  ghost.setAttribute("aria-hidden", "true");
  ghost.textContent = full;

  // Live layer = texte tapé en absolu
  const live = document.createElement("span");
  live.className = "tw-live";
  live.setAttribute("aria-hidden", "true");

  const text = document.createElement("span");
  text.className = "tw-text";
  text.textContent = "";

  const caret = document.createElement("span");
  caret.className = "tw-caret";

  live.append(text, caret);

  title.textContent = "";
  title.append(sr, ghost, live);

  let i = 0;
  let timer = null;
  let dir = 1; // 1 = tape, -1 = efface
  let started = false;
  let pausedByVisibility = false;

  const clearTimer = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };

  const pingDone = () => {
    title.classList.add("tw-done");
    setTimeout(() => title.classList.remove("tw-done"), 900);
  };

  const nextDelayTyping = (ch) => {
    let extra = 0;
    if (/[.!?]/.test(ch)) extra = 220;
    else if (/[,;:]/.test(ch)) extra = 120;
    else if (ch === " ") extra = 25;
    return speed + Math.random() * jitter + extra;
  };

  const nextDelayBack = () => backSpeed + Math.random() * backJitter;

  const tick = () => {
    if (!started) return;

    if (document.hidden) {
      pausedByVisibility = true;
      clearTimer();
      return;
    }
    if (pausedByVisibility) pausedByVisibility = false;

    if (dir === 1) {
      i++;
      text.textContent = full.slice(0, i);

      if (i >= full.length) {
        pingDone();

        if (!loop) {
          caret.style.opacity = "0";
          return;
        }

        clearTimer();
        timer = setTimeout(() => {
          dir = -1;
          tick();
        }, hold);
        return;
      }

      const ch = full[i - 1];
      clearTimer();
      timer = setTimeout(tick, nextDelayTyping(ch));
      return;
    }

    if (dir === -1) {
      i--;
      text.textContent = full.slice(0, Math.max(0, i));

      if (i <= 0) {
        clearTimer();
        timer = setTimeout(() => {
          dir = 1;
          tick();
        }, holdEmpty);
        return;
      }

      clearTimer();
      timer = setTimeout(tick, nextDelayBack());
    }
  };

  const start = () => {
    if (title.dataset.twStarted === "1") return;
    title.dataset.twStarted = "1";
    started = true;
    title.classList.add("tw-enter");
    clearTimer();
    timer = setTimeout(tick, startDelay);
  };

  const isInViewNow = () => {
    const r = title.getBoundingClientRect();
    return r.top < window.innerHeight * 0.9 && r.bottom > 0;
  };

  if (isInViewNow()) {
    requestAnimationFrame(start);
  } else if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        if (e && e.isIntersecting) {
          start();
          io.disconnect();
        }
      },
      { threshold: 0.2, rootMargin: "0px 0px -20% 0px" }
    );
    io.observe(title);
  } else {
    setTimeout(start, 120);
  }

  setTimeout(() => {
    if (title.dataset.twStarted !== "1") start();
  }, 700);

  document.addEventListener(
    "visibilitychange",
    () => {
      if (!document.hidden && started) {
        clearTimer();
        timer = setTimeout(tick, 60);
      }
    },
    { passive: true }
  );
}


    initFooterInView() {
      const footer = document.querySelector(".site-footer");
      if (!footer) return;
      if (footer.dataset.inViewInit === "1") return;
      footer.dataset.inViewInit = "1";

      if (!("IntersectionObserver" in window)) {
        footer.classList.add("is-inview");
        return;
      }

      const io = new IntersectionObserver(
        (entries) => {
          const e = entries[0];
          footer.classList.toggle("is-inview", !!e?.isIntersecting);
        },
        { threshold: 0.08 }
      );

      io.observe(footer);
    }

  }

  document.addEventListener("DOMContentLoaded", () => {
    new CircuitAnimator().init();
  });
})();

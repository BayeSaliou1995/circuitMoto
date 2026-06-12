document.addEventListener("DOMContentLoaded", () => {
  const progressBar = document.querySelector(".programme-progress__bar");
  const sections = Array.from(document.querySelectorAll(".js-programme-section"));
  const cards = Array.from(document.querySelectorAll(".js-programme-card"));
  const navLinks = Array.from(document.querySelectorAll("[data-programme-link]"));

  let ticking = false;
  let currentActiveId = null;

  function updateProgress() {
    if (!progressBar) return;

    const doc = document.documentElement;
    const scrollTop = window.pageYOffset || doc.scrollTop || 0;
    const scrollHeight = doc.scrollHeight - window.innerHeight;
    const ratio = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;

    progressBar.style.width = `${Math.max(0, Math.min(100, ratio))}%`;
  }

  function setActiveLink(id) {
    if (!id || id === currentActiveId) return;
    currentActiveId = id;

    navLinks.forEach((link) => {
      const isActive = link.dataset.programmeLink === id;
      link.classList.toggle("is-active", isActive);
      if (isActive) {
        link.setAttribute("aria-current", "true");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  }

  function getCurrentSectionInView() {
    const scrollY = window.scrollY || window.pageYOffset;
    const offset = 180;

    let activeId = sections.length ? sections[0].id : null;

    for (const section of sections) {
      const sectionTop = section.offsetTop - offset;
      if (scrollY >= sectionTop) {
        activeId = section.id;
      } else {
        break;
      }
    }

    return activeId;
  }

  function revealVisibleElements() {
    const viewportBottom = window.innerHeight + 40;

    sections.forEach((section) => {
      const rect = section.getBoundingClientRect();
      if (rect.top < viewportBottom) {
        section.classList.add("is-visible");
      }
    });

    cards.forEach((card) => {
      const rect = card.getBoundingClientRect();
      if (rect.top < viewportBottom) {
        card.classList.add("is-visible");
      }
    });
  }

  function updateOnScroll() {
    updateProgress();
    revealVisibleElements();

    const activeId = getCurrentSectionInView();
    if (activeId) {
      setActiveLink(activeId);
    }
  }

  function requestTick() {
    if (ticking) return;

    ticking = true;
    window.requestAnimationFrame(() => {
      updateOnScroll();
      ticking = false;
    });
  }

  sections.forEach((section) => section.classList.add("is-visible"));

  cards.forEach((card, index) => {
    card.style.transitionDelay = `${Math.min(index % 4, 3) * 20}ms`;
  });

    navLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
        const id = link.dataset.programmeLink;
        const target = id ? document.getElementById(id) : null;
        if (!target) return;

        e.preventDefault();
        setActiveLink(id);

        const nav = document.querySelector(".site-nav-wrap");
        const navHeight = nav ? nav.offsetHeight : 70;
        const extraOffset = 18;
        const targetTop = target.getBoundingClientRect().top + window.pageYOffset - navHeight - extraOffset;

        window.scrollTo({
        top: targetTop,
        behavior: "smooth",
        });
    });
    });

  updateOnScroll();

  window.addEventListener("scroll", requestTick, { passive: true });
  window.addEventListener("resize", requestTick);
});
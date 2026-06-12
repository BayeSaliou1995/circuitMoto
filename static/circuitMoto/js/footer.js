// static/circuitMoto/js/footer.js

document.addEventListener("DOMContentLoaded", function () {
  const footer = document.getElementById("site-footer");
  if (!footer || !("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        footer.classList.toggle("is-inview", entry.isIntersecting);
      });
    },
    { threshold: 0.15 }
  );

  observer.observe(footer);
});
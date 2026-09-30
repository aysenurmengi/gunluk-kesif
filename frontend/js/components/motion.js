// Elemanlar varsayılan olarak görünürdür; animasyon başarısız olsa da içerik kaybolmaz.
export function createMotion() {
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  let previousCards = [];
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      observer.unobserve(entry.target);
      if (preference.matches) continue;
      const element = entry.target;
      const card = element.classList.contains("card");
      const pop = element.classList.contains("topic");
      const from = pop ? "scale(.6)" : card ? "translateY(60px) rotate(2deg) scale(.96)" : "translateY(32px)";
      element.animate([{ opacity: 0, transform: from }, { opacity: 1, transform: "none" }], {
        duration: 900, delay: Number(element.dataset.delay || 0), easing: "cubic-bezier(.2,.75,.15,1)", fill: "backwards",
      });
    }
  }, { threshold: 0.05 });
  preference.addEventListener("change", () => {
    if (preference.matches) document.getAnimations().forEach((animation) => animation.cancel());
  });
  return {
    observePage() {
      document.querySelectorAll("[data-reveal], .topic").forEach((element, index) => {
        if (element.classList.contains("topic")) element.dataset.delay = (index % 7) * 40;
        observer.observe(element);
      });
    },
    observeCards() {
      previousCards.forEach((element) => observer.unobserve(element));
      previousCards = [...document.querySelectorAll(".card")];
      previousCards.forEach((element, index) => {
        element.dataset.delay = (index % 3) * 90;
        observer.observe(element);
      });
    },
  };
}

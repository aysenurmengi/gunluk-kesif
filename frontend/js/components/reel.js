// Masaüstünde dikey kaydırma kart şeridini ilerletir. Mobilde doğal yatay kaydırma kullanılır.
export function createReel() {
  const section = document.querySelector("#reel");
  const track = document.querySelector("#cards");
  const viewport = document.querySelector("#reel-viewport");
  const previous = document.querySelector("#previous-card");
  const next = document.querySelector("#next-card");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  let savedView = false;
  let maxOffset = 0;
  let frame = 0;
  let lastOffset = 0;
  let skew = 0;
  const clamp = (n, max = 1) => Math.max(0, Math.min(max, n));
  const offset = () => section.dataset.layout === "pinned"
    ? clamp(-section.getBoundingClientRect().top, maxOffset) : viewport.scrollLeft;
  function paint() {
    frame = 0;
    const value = offset();
    if (section.dataset.layout === "pinned") {
      const velocity = Math.max(-6, Math.min(6, (value - lastOffset) * 0.12));
      skew += (velocity - skew) * 0.1;
      track.style.transform = `translateX(${-value}px) skewX(${skew}deg)`;
      if (Math.abs(skew) > 0.02) schedulePaint();
    } else skew = 0;
    lastOffset = value;
    if (!reducedMotion.matches) {
      document.querySelectorAll("[data-parallax]").forEach((element) => {
        const rect = element.parentElement.getBoundingClientRect();
        const distance = innerHeight / 2 - (rect.top + rect.height / 2);
        element.style.transform = `translateY(${Math.max(-30, Math.min(30, distance * Number(element.dataset.parallax)))}px)`;
      });
    }
    const step = (track.firstElementChild?.getBoundingClientRect().width || 400) + 24;
    const count = track.children.length;
    const current = maxOffset && value >= maxOffset - 2 ? count : Math.min(count, Math.floor(value / step) + 1);
    document.querySelector("#reel-count").textContent = `${String(current).padStart(2, "0")} / ${String(count).padStart(2, "0")}`;
    document.querySelector("#reel-fill").style.transform = `scaleX(${maxOffset ? value / maxOffset : 1})`;
    previous.disabled = value <= 1;
    next.disabled = value >= maxOffset - 1;
    const pageHeight = document.documentElement.scrollHeight - innerHeight;
    document.querySelector("#scroll-progress").style.transform = `scaleX(${pageHeight > 0 ? clamp(scrollY / pageHeight) : 0})`;
  }
  function schedulePaint() { if (!frame) frame = requestAnimationFrame(paint); }
  function update(isSaved = savedView) {
    savedView = isSaved;
    section.style.height = "";
    track.style.transform = "";
    section.dataset.layout = savedView || reducedMotion.matches ? "grid" : "native";
    maxOffset = Math.max(0, track.scrollWidth - viewport.clientWidth);
    const cardHeight = track.getBoundingClientRect().height;
    const headerHeight = document.querySelector(".header").offsetHeight;
    if (!section.hidden && !savedView && !reducedMotion.matches && innerWidth >= 900 && cardHeight + 2 * headerHeight + 60 < innerHeight && maxOffset > 0) {
      section.dataset.layout = "pinned";
      section.style.height = `${innerHeight + maxOffset}px`;
      viewport.scrollLeft = 0;
    }
    schedulePaint();
  }
  function moveTo(value) {
    value = clamp(value, maxOffset);
    const behavior = reducedMotion.matches ? "instant" : "smooth";
    if (section.dataset.layout === "pinned") {
      window.scrollTo({ top: scrollY + section.getBoundingClientRect().top + value, behavior });
    } else viewport.scrollTo({ left: value, behavior });
  }
  for (const [button, direction] of [[previous, -1], [next, 1]]) {
    button.addEventListener("click", () => moveTo(offset() + direction * ((track.firstElementChild?.offsetWidth || 400) + 24)));
  }
  // Klavyeyle odaklanan kartın ekran dışında kalmasını önle.
  track.addEventListener("focusin", (event) => {
    if (section.dataset.layout !== "pinned") return;
    const card = event.target.closest(".card");
    const rect = card?.getBoundingClientRect();
    if (rect && (rect.left < 0 || rect.right > innerWidth)) {
      viewport.scrollLeft = 0;
      window.scrollTo({ top: scrollY + section.getBoundingClientRect().top + clamp(card.offsetLeft - 24, maxOffset), behavior: "instant" });
    }
  });
  window.addEventListener("scroll", schedulePaint, { passive: true });
  viewport.addEventListener("scroll", schedulePaint, { passive: true });
  window.addEventListener("resize", () => update());
  reducedMotion.addEventListener("change", () => update());
  document.fonts.ready.then(() => update());
  return { update };
}

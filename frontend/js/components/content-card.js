import { icon } from "./icons.js?v=accounts-1";

// Dışarıdan gelen başlık ve açıklamalar yalnızca textContent ile yazılır.
export function createContentCard(item, { isSaved, onToggleSave, index = 0 }) {
  const card = document.createElement("article");
  card.className = "card";
  card.style.setProperty("--topic-hue", item.topic.hue);
  card.innerHTML = `
    <div class="art"><div class="art-top"><span class="card-number" aria-hidden="true"></span><span class="format-badge">${icon(item.format === "Video" ? "play" : "text", 12)}<span></span></span></div><span class="art-topic"></span></div>
    <div class="card-body"><span class="purpose"></span><h3><a target="_blank" rel="noopener noreferrer"></a></h3>
      <p class="recommendation-reason"><strong>Neden önerildi?</strong> <span></span></p>
      <div class="card-footer"><div class="source-meta"><p class="source-line"></p><p class="published-line"><time></time></p></div><div class="card-actions"><button class="save">${icon("bookmark", 17)}</button><a class="preview" target="_blank" rel="noopener noreferrer"><span></span>${icon("arrow-up-right", 14)}</a></div></div>
    </div>`;
  card.querySelector(".card-number").textContent = String(index + 1).padStart(2, "0");
  card.querySelector(".format-badge span").textContent = item.format;
  card.querySelector(".art-topic").textContent = item.topic.name;
  card.querySelector(".purpose").textContent = item.purpose;
  const title = card.querySelector("h3 a");
  title.textContent = item.title;
  title.href = item.url;
  card.querySelector(".recommendation-reason span").textContent = item.recommendationReason;
  card.querySelector(".recommendation-reason").hidden = !item.recommendationReason;
  card.querySelector(".source-line").textContent = item.sourceName;
  const time = card.querySelector("time");
  time.textContent = item.dateLabel;
  if (item.publishedAt) time.dateTime = item.publishedAt;
  const link = card.querySelector(".preview");
  link.href = item.url;
  const action = item.format === "Video" ? "İzle" : "Oku";
  link.querySelector("span").textContent = action;
  link.setAttribute("aria-label", `${item.title} — ${action} (yeni sekme)`);
  const button = card.querySelector(".save");
  function update(saved) {
    button.setAttribute("aria-pressed", saved);
    button.setAttribute("aria-label", `${item.title}: ${saved ? "kaydı kaldır" : "kaydet"}`);
  }
  update(isSaved);
  // Kaydetme sunucuya gider; yanıt gelene kadar ikinci tıklama yok sayılır.
  let pending = false;
  button.addEventListener("click", async () => {
    if (pending) return;
    pending = true;
    button.setAttribute("aria-busy", "true");
    try { update(await onToggleSave()); }
    finally {
      pending = false;
      button.removeAttribute("aria-busy");
    }
  });
  card.dataset.id = item.id;
  return card;
}

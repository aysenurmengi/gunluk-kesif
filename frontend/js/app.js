import { activeTopics as topics } from "./data/topics.js?v=accounts-1";
import { createContentCard } from "./components/content-card.js?v=accounts-1";
import { icon } from "./components/icons.js?v=accounts-1";
import { createMotion } from "./components/motion.js?v=accounts-1";
import { createReel } from "./components/reel.js?v=accounts-1";
import { createAuthDialog } from "./components/auth-dialog.js?v=accounts-1";
import { fetchContents, toCardItem } from "./services/api.js?v=accounts-1";
import { currentUser, importSaved, listSaved, logout, removeSaved, saveItem } from "./services/account.js?v=accounts-1";
import { selectionNotes } from "./services/selection-notes.js?v=accounts-1";
import { calendarDays, dateLabels, todayInTurkey } from "./services/calendar.js?v=accounts-1";
import { clearLegacySaved, readPreferences, writePreferences } from "./services/preferences.js?v=accounts-1";

const $ = (selector) => document.querySelector(selector);
const preferences = readPreferences();
const { selectedTopics } = preferences;
// Kaydedilenler giriş yapmış kullanıcının hesabından gelir; çıkışta boşalır.
const saved = new Map();
let legacySaved = preferences.legacySaved;
let user = null;
const reel = createReel();
const motion = createMotion();
const authDialog = createAuthDialog();
let contents = [];
let sources = [];
let supportedTopics = [];
let shortfalls = {};
let sourceErrors = {};
let skippedItemCount = 0;
let availableDates = [];
let today = todayInTurkey();
let editionDate = today;
let requestedDate = "";
let currentFormat = "Tümü";
let savedView = false;
let loading = false;
let loaded = false;
let loadError = "";
let refreshTurns = 0;

$("#storage-notice").hidden = !preferences.warning;
$("#storage-notice").textContent = "Bazı tarayıcı kayıtları okunamadı. Yeni seçimlerini bu oturumda kullanabilirsin.";
function persist() {
  const success = writePreferences(selectedTopics);
  $("#storage-notice").hidden = success;
  $("#storage-notice").textContent = "Tarayıcıya kayıt yapılamadı. Konu seçimlerin bu oturumda korunur; sayfa yenilendiğinde kaybolabilir.";
}
function showAccountNotice(message) {
  $("#account-notice").textContent = message;
  $("#account-notice").hidden = !message;
}
function setSaved(originals) {
  saved.clear();
  for (const original of originals) {
    try {
      const item = toCardItem(original);
      saved.set(item.id, item);
    } catch { /* Tanınmayan eski kayıt kartı bozmasın. */ }
  }
}
function renderAccount() {
  $("#account").textContent = user ? "Çıkış yap" : "Giriş yap";
  $("#account").setAttribute("aria-label", user ? `Çıkış yap (${user.email})` : "Giriş yap");
  $("#account-email").textContent = user?.email ?? "";
  $("#account-email").hidden = !user;
  $("#saved-count").hidden = !user;
  $("#saved-count").textContent = saved.size;
}
async function signedIn(account) {
  user = account;
  let originals = await listSaved();
  if (legacySaved.length) {
    // Hesaplardan önce bu tarayıcıda kaydedilenler kaybolmasın.
    const result = await importSaved(legacySaved);
    originals = result.items;
    const moved = legacySaved.length - result.skipped;
    legacySaved = [];
    clearLegacySaved();
    if (moved) showAccountNotice(`Bu tarayıcıda kaydettiğin ${moved} içerik hesabına aktarıldı.`);
  }
  setSaved(originals);
}
function signedOut(message = "") {
  user = null;
  saved.clear();
  if (savedView) setView(false);
  renderAccount();
  renderCards();
  showAccountNotice(message);
}
const sessionReady = (async () => {
  try {
    const account = await currentUser();
    if (account) await signedIn(account);
  } catch (error) {
    showAccountNotice(`Hesap bilgisi alınamadı: ${error.message}`);
  }
  renderAccount();
})();
// Giriş yapılmışsa hemen true; değilse pencereyi açar, vazgeçilirse false döner.
async function requireLogin(reason) {
  await sessionReady;
  if (user) return true;
  const account = await authDialog.open({ reason });
  if (!account) return false;
  try {
    await signedIn(account);
  } catch (error) {
    showAccountNotice(`Giriş yapıldı ama kaydettiklerin yüklenemedi: ${error.message}`);
  }
  renderAccount();
  return true;
}
async function toggleSave(item, index) {
  // Giriş yapmamış biri için tıklama her zaman "kaydet" demektir.
  const wantSaved = !user || !saved.has(item.id);
  const loggedInBefore = Boolean(user);
  if (!(await requireLogin("İçerikleri kaydetmek için giriş yap."))) return false;
  try {
    if (wantSaved && !saved.has(item.id)) setSaved(await saveItem(item.original));
    else if (!wantSaved && saved.has(item.id)) {
      await removeSaved(item.url);
      saved.delete(item.id);
    }
    showAccountNotice("");
  } catch (error) {
    if (error.status === 401) {
      signedOut("Oturumun sona ermiş. Kaydetmek için yeniden giriş yap.");
      return false;
    }
    showAccountNotice(`Kaydetme işlemi tamamlanamadı: ${error.message}`);
  }
  renderAccount();
  // Girişle birlikte hesaptaki diğer kayıtlar da geldiyse bütün kartları güncelle.
  if (savedView || !loggedInBefore) {
    renderCards();
    const cards = [...$("#cards").children];
    const card = cards.find((element) => element.dataset.id === item.id) || cards[Math.min(index, cards.length - 1)];
    (card?.querySelector(".save") || $("#selection-title")).focus({ preventScroll: true });
  }
  return saved.has(item.id);
}
for (const placeholder of document.querySelectorAll("[data-icon]")) placeholder.innerHTML = icon(placeholder.dataset.icon);
for (const topic of topics) {
  const button = document.createElement("button");
  button.className = "topic";
  button.style.setProperty("--topic-hue", topic.hue);
  button.innerHTML = `<span class="topic-dot" aria-hidden="true">${icon("check", 13)}</span><span></span>`;
  button.lastElementChild.textContent = topic.name;
  button.dataset.topic = topic.id;
  button.setAttribute("aria-pressed", selectedTopics.has(topic.id));
  button.addEventListener("click", () => {
    if (selectedTopics.has(topic.id)) selectedTopics.delete(topic.id);
    else selectedTopics.add(topic.id);
    button.setAttribute("aria-pressed", selectedTopics.has(topic.id));
    persist();
    renderCards();
  });
  $("#topics").append(button);
}

function renderDates() {
  const labels = dateLabels(editionDate, today);
  $("#hero-day-name").textContent = `${labels.weekday}${editionDate === today ? " · Bugün" : ""}`;
  $("#hero-month").textContent = labels.month;
  $("#hero-day").textContent = labels.day;
  $("#hero-count").textContent = loading ? "Yükleniyor…" : `${contents.length} keşif`;
  $("#edition-label").textContent = `Türkçe seçki · Sayı ${labels.issue}`;
  const buttons = calendarDays(today, availableDates).map((day) => {
    const button = document.createElement("button");
    button.className = "day";
    button.innerHTML = "<span></span><strong></strong>";
    button.firstElementChild.textContent = day.label;
    button.lastElementChild.textContent = day.day;
    button.dataset.day = day.value;
    button.setAttribute("aria-pressed", editionDate === day.value);
    button.setAttribute("aria-label", `${day.full}${day.available ? " seçkisi" : ": kayıtlı seçki yok"}`);
    button.title = day.available ? day.full : "Bu gün için kayıtlı seçki yok";
    button.disabled = loading || !day.available;
    button.addEventListener("click", () => loadContents(day.value === today ? "" : day.value));
    return button;
  });
  $("#calendar").replaceChildren(...buttons);
  requestAnimationFrame(() => {
    const calendar = $("#calendar");
    const active = calendar.querySelector('[aria-pressed="true"]');
    if (active) calendar.scrollLeft += active.getBoundingClientRect().right - calendar.getBoundingClientRect().right + 4;
  });
  const days = [...new Set(availableDates)].filter((day) => day < today).sort().reverse();
  $("#edition-date").replaceChildren(new Option("Bugün", ""), ...days.map((day) => new Option(dateLabels(day).full, day)));
  $("#edition-date").value = requestedDate === today ? "" : requestedDate;
  $("#edition-date").disabled = loading;
}
function renderCards() {
  const pool = savedView ? [...saved.values()] : contents.filter((item) => selectedTopics.has(item.topic.id));
  const visible = pool.filter((item) => currentFormat === "Tümü" || item.format === currentFormat);
  $("#selection-title").textContent = savedView ? "Kaydettiklerim" : dateLabels(editionDate, today).title;
  $("#list-kicker").textContent = savedView ? "Arşivin" : "Merakının peşinden";
  $("#topic-count").textContent = `${selectedTopics.size} konu seçili`;
  $("#saved-count").textContent = saved.size;
  $("#result-count").textContent = savedView
    ? `${visible.length} / ${saved.size} kayıt · Hesabında saklanır`
    : `${selectedTopics.size} konu seçili · ${visible.length} / ${pool.length} içerik gösteriliyor`;
  $("#cards").setAttribute("aria-busy", loading && !savedView);
  $("#data-status").hidden = savedView || (!loading && !loadError);
  $("#data-status").classList.toggle("error", Boolean(loadError));
  $("#data-status").textContent = loadError || "Günlük seçki yükleniyor…";
  const supported = new Set(supportedTopics.map((id) => id === "yapay-zeka" ? "teknoloji" : id));
  const missing = topics.filter((topic) => selectedTopics.has(topic.id) && !supported.has(topic.id));
  $("#topic-notice").hidden = savedView || !loaded || !missing.length;
  $("#topic-notice").textContent = `Henüz kaynak eklenmeyen konular: ${missing.map((topic) => topic.name).join(", ")}.`;
  const gaps = topics.filter((topic) => selectedTopics.has(topic.id) && shortfalls[topic.id]);
  $("#coverage-notice").hidden = savedView || !loaded || !gaps.length;
  $("#coverage-notice").textContent = `Konu başına en az iki içerik için henüz eksik: ${gaps.map((topic) => `${topic.name} (${shortfalls[topic.id]})`).join(", ")}. Uygun yeni içerik bulununca tamamlanır.`;
  const notes = selectionNotes(sources, sourceErrors, skippedItemCount);
  $("#selection-notes").hidden = savedView || !notes.length;
  $("#selection-notes-label").textContent = `Seçki notları (${notes.length})`;
  $("#source-warning").textContent = notes.join(" ");
  $("#empty").hidden = visible.length > 0 || (!savedView && (loading || Boolean(loadError)));
  let emptyTitle = "Bu gün için yeni içerik yok.";
  let emptyDescription = "Başka bir konu veya kayıtlı tarih seçebilirsin. Yeni öneriler için içerik havuzunda yeterli içerik bulunmayabilir.";
  if (savedView && !saved.size) {
    emptyTitle = "Henüz bir şey kaydetmedin.";
    emptyDescription = "Keşfet sayfasında bir içeriğin yer imi simgesine dokunarak buraya ekleyebilirsin.";
  } else if (!savedView && !selectedTopics.size) {
    emptyTitle = "Önce bir konu seç.";
    emptyDescription = "Yukarıdaki konulardan en az birini seçtiğinde seçkin burada belirir.";
  } else if (currentFormat !== "Tümü") {
    emptyTitle = "Bu filtrede içerik yok.";
    emptyDescription = "Filtreyi “Tümü” yaparak seçkinin tamamını görebilirsin.";
  } else if (!savedView && skippedItemCount && !contents.length) {
    emptyTitle = "İçerikler görüntülenemedi.";
    emptyDescription = "Gelen içeriklerin konu veya bağlantı bilgisi geçersiz. Sayfayı yenileyip yeniden deneyebilirsin.";
  }
  $("#empty h3").textContent = emptyTitle;
  $("#empty p").textContent = emptyDescription;
  $("#cards").replaceChildren(...visible.map((item, index) => createContentCard(item, {
    index, isSaved: saved.has(item.id),
    onToggleSave: () => toggleSave(item, index),
  })));
  $("#reel").hidden = !visible.length;
  reel.update(savedView);
  motion.observeCards();
}
function setFormat(format) {
  currentFormat = format;
  document.querySelectorAll("[data-format]").forEach((button, index) => {
    const active = button.dataset.format === format;
    button.classList.toggle("selected", active);
    button.setAttribute("aria-pressed", active);
    if (active) $(".filters").style.setProperty("--filter-index", index);
  });
  renderCards();
}
function setView(isSaved) {
  savedView = isSaved;
  document.body.classList.toggle("saved-view", isSaved);
  document.querySelectorAll(".discover-only").forEach((element) => { element.hidden = isSaved; });
  $(".nav-track").style.setProperty("--nav-index", isSaved ? 1 : 0);
  for (const id of ["discover", "saved"]) {
    const active = (id === "saved") === isSaved;
    $(`#${id}`).classList.toggle("active", active);
    $(`#${id}`).setAttribute("aria-pressed", active);
  }
  setFormat("Tümü");
  window.scrollTo({ top: 0, behavior: "instant" });
}
async function loadContents(day = requestedDate) {
  if (loading) return;
  requestedDate = day;
  editionDate = day || today;
  loading = true;
  loaded = false;
  loadError = "";
  contents = [];
  sources = [];
  sourceErrors = {};
  supportedTopics = [];
  skippedItemCount = 0;
  $("#selection-notes").open = false;
  $("#reload").disabled = true;
  renderDates();
  renderCards();
  try {
    const result = await fetchContents(day);
    editionDate = result.date;
    today = result.today;
    availableDates = result.available_dates;
    contents = result.items;
    sources = result.sources;
    supportedTopics = result.supported_topics ?? sources.map((source) => source.topic);
    sourceErrors = result.errors ?? {};
    skippedItemCount = result.skippedItemCount;
    shortfalls = result.topic_shortfalls ?? {};
    loaded = true;
  } catch (error) {
    loadError = error.message;
  } finally {
    loading = false;
    $("#reload").disabled = false;
    renderDates();
    renderCards();
  }
}
$("#reload").addEventListener("click", () => {
  $("#reload svg").style.transform = `rotate(${++refreshTurns * 360}deg)`;
  loadContents();
});
$("#edition-date").addEventListener("change", (event) => loadContents(event.target.value));
$("#discover").addEventListener("click", () => setView(false));
async function openSaved() {
  if (!(await requireLogin("Kaydettiklerini görmek için giriş yap."))) return false;
  setView(true);
  return true;
}
$("#saved").addEventListener("click", openSaved);
$("#go-saved").addEventListener("click", async () => {
  if (await openSaved()) $("#selection-title").focus({ preventScroll: true });
});
$("#account").addEventListener("click", async () => {
  await sessionReady;
  if (!user) {
    if (await requireLogin("Kaydettiklerin hesabında saklanır.")) renderCards();
    return;
  }
  try {
    await logout();
    signedOut("Çıkış yaptın. Kaydettiklerin hesabında duruyor.");
  } catch (error) {
    showAccountNotice(`Çıkış yapılamadı: ${error.message}`);
  }
});
sessionReady.then(() => renderCards());
for (const button of document.querySelectorAll("[data-format]")) button.addEventListener("click", () => setFormat(button.dataset.format));
loadContents();
motion.observePage();

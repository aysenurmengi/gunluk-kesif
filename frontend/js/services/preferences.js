import { activeTopics } from "../data/topics.js?v=accounts-1";
import { toCardItem } from "./api.js?v=accounts-1";
const TOPICS_KEY = "gk-v2-topics";
// Hesaplardan önce kayıtlar tarayıcıda tutuluyordu; ilk girişte hesaba aktarılır.
const LEGACY_SAVED_KEY = "gk-v2-saved";
const allTopics = activeTopics.map((topic) => topic.id);
// Sonradan eklenen konular: önceden bütün konuları seçmiş kullanıcıda otomatik seçilir.
const ADDED_TOPICS = ["finans", "bilim"];

// localStorage erişimi engellense bile uygulama bellekte çalışmaya devam eder.
export function readPreferences(storage) {
  let selectedTopics = new Set(allTopics);
  const legacySaved = [];
  let warning = false;
  try {
    storage ??= globalThis.localStorage;
    const rawTopics = storage.getItem(TOPICS_KEY);
    if (rawTopics !== null) {
      const ids = JSON.parse(rawTopics);
      if (!Array.isArray(ids)) throw new Error("Geçersiz tercihler");
      selectedTopics = new Set(ids.map((id) => id === "yapay-zeka" ? "teknoloji" : id).filter((id) => allTopics.includes(id)));
      // Önceden bütün konuları seçen kullanıcı yeni eklenen konuları da görür.
      if (allTopics.filter((id) => !ADDED_TOPICS.includes(id)).every((id) => selectedTopics.has(id))) {
        for (const id of ADDED_TOPICS) selectedTopics.add(id);
      }
    }
  } catch { warning = true; }
  try {
    storage ??= globalThis.localStorage;
    const entries = JSON.parse(storage.getItem(LEGACY_SAVED_KEY) || "[]");
    if (!Array.isArray(entries)) throw new Error("Geçersiz kayıtlar");
    const seen = new Set();
    for (const original of entries) {
      try {
        const item = toCardItem(original);
        if (!seen.has(item.id)) legacySaved.push(original);
        seen.add(item.id);
      } catch { warning = true; }
    }
  } catch { warning = true; }
  return { selectedTopics, legacySaved, warning };
}
export function writePreferences(selectedTopics, storage) {
  try {
    storage ??= globalThis.localStorage;
    storage.setItem(TOPICS_KEY, JSON.stringify([...selectedTopics]));
    return true;
  } catch { return false; }
}
export function clearLegacySaved(storage) {
  try {
    storage ??= globalThis.localStorage;
    storage.removeItem(LEGACY_SAVED_KEY);
    return true;
  } catch { return false; }
}

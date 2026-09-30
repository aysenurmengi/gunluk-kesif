import { topics } from "../data/topics.js?v=accounts-1";

const dateFormatter = new Intl.DateTimeFormat("tr-TR", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Istanbul",
});

class InvalidContentError extends Error {}
// Konu içindeki yeri: her başlıkta bir gelişme, bir video, bir derinlemesine yazı hedeflenir.
const ROLE_LABELS = { gelisme: "Yeni gelişme", video: "İzlemeye değer", derinlik: "Biraz derinleş" };

// Backend verisini mevcut kart tasarımının kullandığı alanlara dönüştür.
export function toCardItem(item) {
  if (!item || typeof item !== "object" || typeof item.title !== "string" || !item.title.trim()) {
    throw new InvalidContentError("İçerik başlığı eksik.");
  }
  let url;
  try { url = new URL(item.url); }
  catch { throw new InvalidContentError("İçerik bağlantısı geçersiz."); }
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new InvalidContentError("İçerik bağlantısı desteklenmiyor.");
  }
  const topicId = item.topic === "yapay-zeka" ? "teknoloji" : item.topic;
  const topic = topics.find((topic) => topic.id === topicId);
  if (!topic) throw new InvalidContentError("İçeriğin konusu tanınmıyor.");
  const date = item.published_at ? new Date(item.published_at) : null;
  const validDate = date && !Number.isNaN(date.getTime());
  return {
    original: item,
    id: item.url, url: item.url, title: item.title, topic,
    format: item.content_type === "video" ? "Video" : "Yazı",
    purpose: item.topic === "guncel"
      ? (item.news_scope === "turkiye" ? "Türkiye gündemi" : item.news_scope === "dunya" ? "Dünya gündemi" : "Gündemi yakala")
      : item.topic === "spor" && item.content_type === "news" ? "Spor gündemi"
      : ROLE_LABELS[item.role]
        ?? (item.content_type === "news" ? "Yeni gelişme" : item.purpose === "evergreen" ? "Biraz derinleş" : "Gündemi yakala"),
    sourceName: item.source_name,
    publishedAt: validDate ? date.toISOString() : null,
    dateLabel: validDate
      ? (item.publication_date_only
        ? new Intl.DateTimeFormat("tr-TR", { dateStyle: "long", timeZone: "Europe/Istanbul" }).format(date)
        : `${dateFormatter.format(date)} TSİ`)
      : "Yayın tarihi bilinmiyor",
  };
}

export async function fetchContents(day = "") {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(`/api/recommendations${day ? `?day=${encodeURIComponent(day)}` : ""}`, { signal: controller.signal, cache: "no-store" });
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("API yanıtı alınamadı. Eski sunucuyu kapatıp yeni başlatma komutunu kullan.");
    }
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail?.message || `İçerikler yüklenemedi (HTTP ${response.status}).`);
    }
    if (!Array.isArray(payload.items) || !Array.isArray(payload.sources)) {
      throw new Error("Sunucunun içerik yanıtı beklenen biçimde değil.");
    }
    const items = [];
    let skippedItemCount = 0;
    for (const item of payload.items) {
      try { items.push(toCardItem(item)); }
      catch (error) {
        if (!(error instanceof InvalidContentError)) throw error;
        skippedItemCount += 1;
      }
    }
    return { ...payload, items, skippedItemCount };
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Kaynakları okumak uzun sürdü. Yeniden deneyebilirsin.");
    if (error instanceof TypeError) throw new Error("Sunucuya ulaşılamadı. Yerel sunucunun açık olduğunu kontrol et.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

import test from "node:test";
import assert from "node:assert/strict";
import { fetchContents, toCardItem } from "../js/services/api.js";

const item = {
  title: "Örnek başlık", url: "https://example.com/haber", topic: "ekonomi",
  source_name: "Örnek kaynak", content_type: "article", purpose: "current",
  published_at: "2026-09-29T17:02:00Z",
};

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { "content-type": "application/json" } });
}

test("UTC date displays in Turkish with Istanbul time", () => {
  const card = toCardItem(item);
  assert.equal(card.id, item.url);
  assert.equal(card.topic.name, "Ekonomi");
  assert.match(card.dateLabel, /20:02/);
  assert.match(card.dateLabel, /TSİ/);
  assert.equal(card.sourceName, "Örnek kaynak");
});

test("missing and invalid dates do not become today", () => {
  for (const value of [null, "", "bad-date"]) {
    const card = toCardItem({ ...item, published_at: value });
    assert.equal(card.publishedAt, null);
    assert.equal(card.dateLabel, "Yayın tarihi bilinmiyor");
  }
});

test("non-web links cannot become clickable source links", () => {
  for (const url of ["javascript:alert(1)", "file:///C:/test.txt", "data:text/html,test"]) {
    assert.throws(() => toCardItem({ ...item, url }), /desteklenmiyor/);
  }
});

test("video format and learning purpose stay independent", () => {
  assert.equal(toCardItem({ ...item, content_type: "video" }).purpose, "Gündemi yakala");
  assert.equal(toCardItem({ ...item, purpose: "evergreen" }).format, "Yazı");
});

test("fetch consumes real API structure and preserves warnings", async (t) => {
  t.mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(path, "/api/recommendations");
    assert.equal(options.cache, "no-store");
    return jsonResponse({ items: [item], sources: [], errors: { "trt-spor": "Hata" } });
  });
  const result = await fetchContents();
  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].title, item.title);
  assert.equal(result.errors["trt-spor"], "Hata");
});

test("503 API message is shown instead of demo content", async (t) => {
  t.mock.method(globalThis, "fetch", async () => jsonResponse({ detail: { message: "Kaynaklar okunamadı." } }, 503));
  await assert.rejects(fetchContents(), /Kaynaklar okunamadı/);
});

test("old static server response gives a useful error", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>404</html>", { status: 404, headers: { "content-type": "text/html" } }));
  await assert.rejects(fetchContents(), /Eski sunucuyu kapat/);
});

test("connection failure and abort become readable errors", async (t) => {
  const mocked = t.mock.method(globalThis, "fetch", async () => { throw new TypeError("fetch failed"); });
  await assert.rejects(fetchContents(), /Sunucuya ulaşılamadı/);
  mocked.mock.mockImplementation(async () => { throw new DOMException("aborted", "AbortError"); });
  await assert.rejects(fetchContents(), /uzun sürdü/);
});

test("archive selection requests the stored date", async (t) => {
  t.mock.method(globalThis, "fetch", async (path) => {
    assert.equal(path, "/api/recommendations?day=2026-09-29");
    return jsonResponse({ items: [], sources: [] });
  });
  await fetchContents("2026-09-29");
});

test("old AI archive entries map to Technology without losing their reason", () => {
  const card = toCardItem({ ...item, topic: "yapay-zeka", recommendation_reason: "Bir kavramı açıklıyor." });
  assert.equal(card.topic.id, "teknoloji");
  assert.equal(card.recommendationReason, "Bir kavramı açıklıyor.");
});

test("date-only sources do not display a fabricated publication time", () => {
  const card = toCardItem({ ...item, published_at: "2021-02-05T00:00:00+03:00", publication_date_only: true });
  assert.match(card.dateLabel, /5 Şubat 2021/);
  assert.doesNotMatch(card.dateLabel, /TSİ|00:00/);
});

test("unknown topic does not hide valid economy and technology cards", async (t) => {
  t.mock.method(globalThis, "fetch", async () => jsonResponse({
    items: [item, { ...item, topic: "unknown" }, { ...item, topic: "teknoloji" }, { ...item, topic: "yapay-zeka" }], sources: [],
  }));
  const result = await fetchContents();
  assert.deepEqual(result.items.map((card) => card.topic.id), ["ekonomi", "teknoloji", "teknoloji"]);
  assert.equal(result.skippedItemCount, 1);
});

test("invalid rows and unsafe URLs are skipped and reported individually", async (t) => {
  t.mock.method(globalThis, "fetch", async () => jsonResponse({
    items: [null, { ...item, url: "javascript:alert(1)" }, { ...item, url: "bad" }, item], sources: [],
  }));
  const result = await fetchContents();
  assert.equal(result.items.length, 1);
  assert.equal(result.skippedItemCount, 3);
});

test("all rejected rows are distinguishable from a genuinely empty day", async (t) => {
  const mocked = t.mock.method(globalThis, "fetch", async () => jsonResponse({ items: [{ ...item, topic: "unknown" }], sources: [] }));
  const rejected = await fetchContents();
  assert.equal(rejected.items.length, 0);
  assert.equal(rejected.skippedItemCount, 1);
  mocked.mock.mockImplementation(async () => jsonResponse({ items: [], sources: [] }));
  assert.equal((await fetchContents()).skippedItemCount, 0);
});

test("collection failures are described as historical notes, not missing topic content", async () => {
  const { selectionNotes } = await import("../js/services/selection-notes.js");
  assert.deepEqual(selectionNotes([], {}), []);
  const notes = selectionNotes([{ id: "mesele", name: "Mesele Ekonomi" }], { mesele: "Timeout" });
  assert.equal(notes.length, 1);
  assert.match(notes[0], /seçki hazırlanırken/);
  assert.match(notes[0], /kaydedilmiş içerikler yine gösterilebilir/);
  assert.doesNotMatch(notes[0], /Liste eksik olabilir/);
});

test("news cards distinguish Turkey, world and sports without changing format", () => {
  const news = { ...item, content_type: "news", topic: "guncel" };
  assert.equal(toCardItem({ ...news, news_scope: "turkiye" }).purpose, "Türkiye gündemi");
  assert.equal(toCardItem({ ...news, news_scope: "dunya" }).purpose, "Dünya gündemi");
  assert.equal(toCardItem({ ...news, topic: "spor" }).purpose, "Spor gündemi");
  assert.equal(toCardItem(news).format, "Yazı");
});

test("topic cards show their role; news keeps its scope label", () => {
  assert.equal(toCardItem({ ...item, role: "gelisme" }).purpose, "Yeni gelişme");
  assert.equal(toCardItem({ ...item, role: "video", content_type: "video" }).purpose, "İzlemeye değer");
  assert.equal(toCardItem({ ...item, role: "derinlik" }).purpose, "Biraz derinleş");
  assert.equal(toCardItem({ ...item, topic: "guncel", content_type: "news", news_scope: "dunya", role: "gelisme" }).purpose, "Dünya gündemi");
  // Rol alanı olmayan eski kayıtlar.
  assert.equal(toCardItem({ ...item, purpose: "evergreen" }).purpose, "Biraz derinleş");
  assert.equal(toCardItem({ ...item, topic: "ekonomi", content_type: "news" }).purpose, "Yeni gelişme");
  assert.equal(toCardItem({ ...item, topic: "spor", content_type: "news", role: "gelisme" }).purpose, "Spor gündemi");
});

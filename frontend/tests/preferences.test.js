import test from "node:test";
import assert from "node:assert/strict";
import { calendarDays, dateLabels } from "../js/services/calendar.js";
import { clearLegacySaved, readPreferences, writePreferences } from "../js/services/preferences.js";
import { toCardItem } from "../js/services/api.js";
const makeStorage = (initial = {}) => {
  const values = new Map(Object.entries(initial));
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
};
const original = { title: "Bir ekonomi yazısı", url: "https://example.com/article", topic: "ekonomi", content_type: "article", source_name: "Örnek" };
test("calendar crosses a year boundary and only enables stored dates and today", () => {
  const days = calendarDays("2027-01-02", ["2026-12-31"]);
  assert.deepEqual(days.map((day) => day.value), ["2026-12-27", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"]);
  assert.deepEqual(days.filter((day) => day.available).map((day) => day.value), ["2026-12-31", "2027-01-02"]);
  assert.equal(days.at(-1).label, "Bugün");
});
test("edition number and archive title use the selected date, including leap years", () => {
  assert.equal(dateLabels("2026-09-30").issue, 273);
  assert.equal(dateLabels("2028-12-31").issue, 366);
  assert.equal(dateLabels("2027-01-01").issue, 1);
  assert.equal(dateLabels("2026-09-29", "2026-09-30").title, "29 Eylül seçkisi");
});
test("empty topic preferences persist instead of resetting to all topics", () => {
  const storage = makeStorage();
  assert.equal(writePreferences(new Set(), storage), true);
  assert.equal(readPreferences(storage).selectedTopics.size, 0);
});
test("pre-account bookmarks are read once for import and can then be cleared", () => {
  const storage = makeStorage({ "gk-v2-saved": JSON.stringify([original, original]) });
  writePreferences(new Set(["ekonomi"]), storage);
  const restored = readPreferences(storage);
  assert.deepEqual(restored.legacySaved, [original]);
  assert.deepEqual([...restored.selectedTopics], ["ekonomi"]);
  assert.equal(clearLegacySaved(storage), true);
  assert.deepEqual(readPreferences(storage).legacySaved, []);
  assert.deepEqual([...readPreferences(storage).selectedTopics], ["ekonomi"]);
});
test("old topic IDs migrate and unknown topics are ignored", () => {
  const prefs = readPreferences(makeStorage({ "gk-v2-topics": '["yapay-zeka", "unknown"]' }));
  assert.deepEqual([...prefs.selectedTopics], ["teknoloji"]);
});
test("corrupt topics do not hide independently valid bookmarks", () => {
  const prefs = readPreferences(makeStorage({ "gk-v2-topics": "{", "gk-v2-saved": JSON.stringify([original]) }));
  assert.equal(prefs.selectedTopics.size, 8);
  assert.equal(prefs.legacySaved.length, 1);
  assert.equal(prefs.warning, true);
});
test("unsafe saved links are rejected individually", () => {
  const prefs = readPreferences(makeStorage({ "gk-v2-saved": JSON.stringify([{ ...original, url: "javascript:alert(1)" }, original, original]) }));
  assert.equal(prefs.legacySaved.length, 1);
  assert.equal(prefs.warning, true);
});
test("blocked storage is nonfatal and saving reports failure", () => {
  const storage = { getItem() { throw new Error("Blocked"); }, setItem() { throw new Error("Quota"); } };
  const prefs = readPreferences(storage);
  assert.equal(prefs.selectedTopics.size, 8);
  assert.equal(prefs.legacySaved.length, 0);
  assert.equal(prefs.warning, true);
  assert.equal(writePreferences(prefs.selectedTopics, storage), false);
  assert.equal(clearLegacySaved(storage), false);
});

test("all old topics opt into Finance; a custom subset stays unchanged", () => {
  const old = ["guncel", "teknoloji", "ekonomi", "yemek", "moda", "kitap", "spor"];
  const restored = readPreferences(makeStorage({ "gk-v2-topics": JSON.stringify(old) }));
  assert.equal(restored.selectedTopics.has("finans"), true);
  const custom = readPreferences(makeStorage({ "gk-v2-topics": '["ekonomi"]' }));
  assert.deepEqual([...custom.selectedTopics], ["ekonomi"]);
});
test("Finance is a valid independent card topic", () => {
  assert.equal(toCardItem({ ...original, topic: "finans" }).topic.name, "Finans");
});

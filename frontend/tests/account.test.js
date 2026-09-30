import test from "node:test";
import assert from "node:assert/strict";
import { currentUser, login, removeSaved, saveItem } from "../js/services/account.js";

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { "content-type": "application/json" } });
}

test("anonymous visitor is a normal state, not an error", async (t) => {
  t.mock.method(globalThis, "fetch", async () => jsonResponse({ user: null }));
  assert.equal(await currentUser(), null);
});

test("login sends credentials as JSON with same-origin cookies", async (t) => {
  t.mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(path, "/api/auth/login");
    assert.equal(options.method, "POST");
    assert.equal(options.credentials, "same-origin");
    assert.deepEqual(JSON.parse(options.body), { email: "okur@example.com", password: "parola-123" });
    return jsonResponse({ user: { id: 1, email: "okur@example.com" } });
  });
  assert.deepEqual(await login("okur@example.com", "parola-123"), { id: 1, email: "okur@example.com" });
});

test("server messages and status codes reach the interface", async (t) => {
  t.mock.method(globalThis, "fetch", async () => jsonResponse({ detail: { message: "E-posta veya parola hatalı." } }, 401));
  await assert.rejects(login("a@example.com", "x"), (error) => error.status === 401 && /hatalı/.test(error.message));
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => jsonResponse({ detail: [{ msg: "Field required" }] }, 422));
  await assert.rejects(login("", ""), /Girilen bilgiler geçersiz/);
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => { throw new TypeError("fetch failed"); });
  await assert.rejects(login("a@example.com", "x"), (error) => error.status === 0 && /Sunucuya ulaşılamadı/.test(error.message));
});

test("save and remove use the saved-items endpoints", async (t) => {
  const item = { title: "Yazı", url: "https://example.com/a?b=1&c=2" };
  const calls = [];
  t.mock.method(globalThis, "fetch", async (path, options) => {
    calls.push([options.method, path]);
    return options.method === "DELETE" ? new Response(null, { status: 204 }) : jsonResponse({ items: [item] });
  });
  assert.deepEqual(await saveItem(item), [item]);
  assert.equal(await removeSaved(item.url), null);
  assert.deepEqual(calls, [["PUT", "/api/saved"], ["DELETE", `/api/saved?url=${encodeURIComponent(item.url)}`]]);
});

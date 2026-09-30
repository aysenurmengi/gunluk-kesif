// Hesap ve kaydedilenler API'si. Oturum HttpOnly çerezde tutulur; JavaScript göremez.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method, cache: "no-store", credentials: "same-origin",
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Sunucuya ulaşılamadı. Yerel sunucunun açık olduğunu kontrol et.", 0);
  }
  if (response.status === 204) return null;
  const payload = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const message = typeof payload?.detail?.message === "string" ? payload.detail.message
      : response.status === 422 ? "Girilen bilgiler geçersiz."
        : `İşlem tamamlanamadı (HTTP ${response.status}).`;
    throw new ApiError(message, response.status);
  }
  return payload;
}

export const currentUser = async () => (await request("/api/auth/me")).user;
export const login = async (email, password) => (await request("/api/auth/login", { method: "POST", body: { email, password } })).user;
export const register = async (email, password) => (await request("/api/auth/register", { method: "POST", body: { email, password } })).user;
export const logout = () => request("/api/auth/logout", { method: "POST" });
export const listSaved = async () => (await request("/api/saved")).items;
export const saveItem = async (item) => (await request("/api/saved", { method: "PUT", body: { item } })).items;
export const importSaved = (items) => request("/api/saved/import", { method: "POST", body: { items } });
export const removeSaved = (url) => request(`/api/saved?url=${encodeURIComponent(url)}`, { method: "DELETE" });

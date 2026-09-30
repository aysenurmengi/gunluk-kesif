import { login, register } from "../services/account.js?v=accounts-1";

// Yerleşik <dialog>: odak pencerede kalır, Esc kapatır. Kapatılırsa sonuç null olur.
export function createAuthDialog() {
  const dialog = document.querySelector("#auth-dialog");
  const form = document.querySelector("#auth-form");
  const email = document.querySelector("#auth-email");
  const password = document.querySelector("#auth-password");
  const confirm = document.querySelector("#auth-password-confirm");
  const confirmField = document.querySelector("#auth-confirm-field");
  const show = document.querySelector("#auth-show");
  const submit = document.querySelector("#auth-submit");
  const error = document.querySelector("#auth-error");
  const tabs = [...dialog.querySelectorAll("[data-auth-mode]")];
  let mode = "login";
  let resolve = null;
  let opener = null;
  let busy = false;

  function setMode(next) {
    mode = next;
    const label = mode === "login" ? "Giriş yap" : "Hesap oluştur";
    document.querySelector("#auth-title").textContent = label;
    submit.textContent = label;
    password.autocomplete = mode === "login" ? "current-password" : "new-password";
    document.querySelector("#auth-hint").hidden = mode === "login";
    confirmField.hidden = mode === "login";
    confirm.required = mode === "register";
    for (const tab of tabs) tab.setAttribute("aria-pressed", tab.dataset.authMode === mode);
    showError("");
  }
  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }
  function finish(user) {
    resolve?.(user);
    resolve = null;
  }

  function setVisible(visible) {
    show.checked = visible;
    for (const field of [password, confirm]) field.type = visible ? "text" : "password";
  }

  for (const tab of tabs) tab.addEventListener("click", () => setMode(tab.dataset.authMode));
  show.addEventListener("change", () => setVisible(show.checked));
  document.querySelector("#auth-close").addEventListener("click", () => dialog.close());
  // Pencerenin dışına (arka plana) tıklamak da kapatır.
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => {
    finish(null);
    if (opener?.isConnected) opener.focus({ preventScroll: true });
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    if (!email.value.trim() || !password.value) {
      showError("E-posta ve parolanı yaz.");
      (email.value.trim() ? password : email).focus();
      return;
    }
    if (mode === "register" && password.value.length < 8) {
      showError("Parola en az 8 karakter olmalı.");
      password.focus();
      return;
    }
    if (mode === "register" && password.value !== confirm.value) {
      showError("Parolalar eşleşmiyor. İki alana da aynı parolayı yaz.");
      confirm.select();
      return;
    }
    busy = true;
    submit.setAttribute("aria-busy", "true");
    showError("");
    try {
      const user = await (mode === "login" ? login : register)(email.value, password.value);
      finish(user);
      dialog.close();
    } catch (failure) {
      showError(failure.message);
      password.select();
    } finally {
      busy = false;
      submit.removeAttribute("aria-busy");
    }
  });

  return {
    open({ reason = "Kaydettiklerin hesabında saklanır.", initialMode = "login" } = {}) {
      finish(null);
      opener = document.activeElement;
      document.querySelector("#auth-reason").textContent = reason;
      password.value = "";
      confirm.value = "";
      setVisible(false);
      setMode(initialMode);
      dialog.showModal();
      (email.value ? password : email).focus();
      return new Promise((done) => { resolve = done; });
    },
  };
}

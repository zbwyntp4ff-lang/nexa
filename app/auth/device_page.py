"""Self-contained phone page for QR device login (served by FastAPI on LAN)."""

DEVICE_PAGE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <title>NEXA — подтверждение входа</title>
  <style>
    :root { color-scheme: dark; }
    body { margin:0; font-family: system-ui, sans-serif; background:#12121c; color:#f4f4fb;
      min-height:100dvh; display:flex; align-items:center; justify-content:center; padding:24px; }
    .card { width:100%; max-width:22rem; background:#1c1c28; border:1px solid #2e2e40; border-radius:16px; padding:24px; }
    h1 { font-size:1.15rem; margin:0 0 8px; }
    p { color:#a8a8bf; font-size:.9rem; line-height:1.4; }
    label { display:block; font-size:.8rem; margin:12px 0 6px; }
    input { width:100%; box-sizing:border-box; height:44px; border-radius:10px; border:1px solid #3a3a52;
      background:#12121c; color:#fff; padding:0 12px; font-size:16px; }
    button { width:100%; height:46px; margin-top:16px; border:0; border-radius:10px; background:#6c5ce7;
      color:#fff; font-weight:600; font-size:1rem; }
    button:disabled { opacity:.5; }
    .err { color:#ff6b7a; font-size:.85rem; margin-top:10px; white-space:pre-wrap; }
    .ok { color:#3dd6c6; }
    .code { font-family: ui-monospace, monospace; letter-spacing:.2em; font-size:1.3rem; text-align:center; margin:12px 0; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Подтверждение NEXA</h1>
    <p>Тот же email (или имя) и пароль, что на компьютере.</p>
    <div class="code" id="codeLabel"></div>
    <form id="form">
      <label>Email или имя пользователя</label>
      <input id="email" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" required/>
      <label>Пароль</label>
      <input id="password" type="password" autocomplete="current-password" required/>
      <button type="submit" id="btn">Войти и подтвердить</button>
      <p class="err" id="err" hidden></p>
      <p class="ok" id="ok" hidden>Готово. Вернись к компьютеру — вход должен завершиться сам.</p>
    </form>
  </div>
  <script>
    const params = new URLSearchParams(location.search);
    const code = (params.get("code") || "").toUpperCase();
    document.getElementById("codeLabel").textContent = code || "—";
    const err = document.getElementById("err");
    const ok = document.getElementById("ok");
    const btn = document.getElementById("btn");
    function showErr(msg) { err.hidden = false; ok.hidden = true; err.textContent = msg; }
    function apiMessage(data, fallback) {
      if (!data || typeof data !== "object") return fallback;
      if (typeof data.message === "string" && data.message) return data.message;
      if (typeof data.error === "string" && data.error === "InvalidCredentials")
        return "Неверный email, имя или пароль";
      if (typeof data.error === "string" && data.error === "DeviceLoginError")
        return "Код устарел. На компьютере нажми QR ещё раз и сканируй новый.";
      return fallback;
    }
    document.getElementById("form").addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      btn.disabled = true;
      try {
        if (!code) throw new Error("В ссылке нет кода. Отсканируй QR ещё раз.");
        const res = await fetch("/api/v1/auth/device/login", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value,
            user_code: code
          })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(apiMessage(data, "Не удалось войти"));
        ok.hidden = false;
        btn.hidden = true;
      } catch (ex) {
        showErr(ex.message || "Ошибка");
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""

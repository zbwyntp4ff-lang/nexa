"""Minimal playable car + coins HTML5 game (no npm)."""
from __future__ import annotations

INDEX_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Car Coins — NEXA</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <main>
    <header>
      <h1>Car Coins</h1>
      <p>Стрелки / WASD — езда · собирай монеты</p>
    </header>
    <div class="hud">
      <span id="score">Монеты: 0</span>
      <span id="status">Играй!</span>
    </div>
    <canvas id="game" width="720" height="420" aria-label="Игровое поле"></canvas>
  </main>
  <script src="main.js"></script>
</body>
</html>
"""

STYLE_CSS = """:root {
  color-scheme: dark;
  --bg: #0f1419;
  --panel: #1a2332;
  --accent: #f5c542;
  --car: #3dd6c6;
  --road: #2a3344;
  --text: #e8eef7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: radial-gradient(ellipse at top, #1b2738, var(--bg));
  color: var(--text);
}
main { width: min(760px, 96vw); }
header h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
header p { margin: 0 0 0.75rem; opacity: 0.75; font-size: 0.9rem; }
.hud {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--panel);
  border-radius: 10px;
  font-variant-numeric: tabular-nums;
}
#game {
  width: 100%;
  height: auto;
  display: block;
  background: var(--road);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.35);
}
"""

MAIN_JS = """(() => {
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const scoreEl = document.getElementById("score");
  const statusEl = document.getElementById("status");

  const car = { x: 360, y: 320, w: 36, h: 56, speed: 0, angle: -Math.PI / 2 };
  const keys = new Set();
  let coins = [];
  let enemies = [];
  let score = 0;
  let last = performance.now();
  let alive = true;

  function spawnCoins(n = 8) {
    coins = [];
    for (let i = 0; i < n; i++) {
      coins.push({
        x: 40 + Math.random() * (canvas.width - 80),
        y: 40 + Math.random() * (canvas.height - 120),
        r: 10,
      });
    }
  }

  function spawnEnemies(n = 0) {
    enemies = [];
    for (let i = 0; i < n; i++) {
      enemies.push({
        x: 60 + Math.random() * (canvas.width - 120),
        y: 60 + Math.random() * (canvas.height - 160),
        r: 14,
        vx: (Math.random() * 40 + 20) * (Math.random() < 0.5 ? -1 : 1),
        vy: (Math.random() * 40 + 20) * (Math.random() < 0.5 ? -1 : 1),
      });
    }
  }

  function reset() {
    score = 0;
    alive = true;
    car.x = 360;
    car.y = 320;
    car.speed = 0;
    car.angle = -Math.PI / 2;
    spawnCoins();
    spawnEnemies(window.__NEXA_ENEMIES__ || 0);
    scoreEl.textContent = "Монеты: 0";
    statusEl.textContent = "Играй!";
  }

  window.addEventListener("keydown", (e) => {
    keys.add(e.key.toLowerCase());
    if (["arrowup","arrowdown","arrowleft","arrowright"," "].includes(e.key.toLowerCase())) {
      e.preventDefault();
    }
  });
  window.addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));

  function update(dt) {
    if (!alive) {
      if (keys.has("r")) reset();
      return;
    }
    const accel = 180;
    const turn = 2.6;
    const friction = 0.98;
    if (keys.has("arrowup") || keys.has("w")) car.speed += accel * dt;
    if (keys.has("arrowdown") || keys.has("s")) car.speed -= accel * dt;
    if (keys.has("arrowleft") || keys.has("a")) car.angle -= turn * dt * Math.sign(car.speed || 1);
    if (keys.has("arrowright") || keys.has("d")) car.angle += turn * dt * Math.sign(car.speed || 1);
    car.speed *= friction;
    car.x += Math.cos(car.angle) * car.speed * dt;
    car.y += Math.sin(car.angle) * car.speed * dt;
    car.x = Math.max(20, Math.min(canvas.width - 20, car.x));
    car.y = Math.max(20, Math.min(canvas.height - 20, car.y));

    for (const e of enemies) {
      e.x += e.vx * dt;
      e.y += e.vy * dt;
      if (e.x < 20 || e.x > canvas.width - 20) e.vx *= -1;
      if (e.y < 20 || e.y > canvas.height - 20) e.vy *= -1;
      const dx = e.x - car.x;
      const dy = e.y - car.y;
      if (dx * dx + dy * dy < (e.r + 20) ** 2) {
        alive = false;
        statusEl.textContent = "Столкновение! R — рестарт";
      }
    }

    coins = coins.filter((c) => {
      const dx = c.x - car.x;
      const dy = c.y - car.y;
      if (dx * dx + dy * dy < (c.r + 22) ** 2) {
        score += 1;
        scoreEl.textContent = "Монеты: " + score;
        if (score >= 8) statusEl.textContent = "Победа! Нажми R для рестарта";
        return false;
      }
      return true;
    });
    if (coins.length === 0 && score < 8) spawnCoins(4);
    if (keys.has("r")) reset();
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 2;
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
    for (const c of coins) {
      ctx.beginPath();
      ctx.fillStyle = "#f5c542";
      ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#8a6a12";
      ctx.font = "12px sans-serif";
      ctx.fillText("$", c.x - 4, c.y + 4);
    }
    for (const e of enemies) {
      ctx.beginPath();
      ctx.fillStyle = "#e85d5d";
      ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.save();
    ctx.translate(car.x, car.y);
    ctx.rotate(car.angle + Math.PI / 2);
    ctx.fillStyle = "#3dd6c6";
    ctx.fillRect(-car.w / 2, -car.h / 2, car.w, car.h);
    ctx.fillStyle = "#0f1419";
    ctx.fillRect(-car.w / 2 + 6, -car.h / 2 + 8, car.w - 12, 16);
    ctx.restore();
  }

  function loop(now) {
    const dt = Math.min(0.033, (now - last) / 1000);
    last = now;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }

  reset();
  requestAnimationFrame(loop);
})();
"""


def files_for_car_coins() -> dict[str, str]:
    return {
        "index.html": INDEX_HTML,
        "style.css": STYLE_CSS,
        "main.js": MAIN_JS,
        "README.md": (
            "# Car Coins\n\n"
            "Управление: стрелки или WASD. Собирай монеты. R — рестарт.\n\n"
            "Открой `index.html` через preview NEXA.\n"
        ),
    }

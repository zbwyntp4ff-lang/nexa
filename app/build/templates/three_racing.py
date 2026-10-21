"""Playable Three.js racing game (CDN) — Part 13."""
from __future__ import annotations

from app.build.templates.three_common import STYLE_CSS, index_html, scene_json

MAIN_JS = r"""(() => {
  if (typeof THREE === "undefined") {
    document.getElementById("status").textContent = "Three.js failed to load";
    return;
  }
  const canvas = document.getElementById("game");
  const statusEl = document.getElementById("status");
  const scoreEl = document.getElementById("score");
  const overlay = document.getElementById("overlay");
  const overlayText = document.getElementById("overlay-text");
  const restartBtn = document.getElementById("restart");

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a1020);
  scene.fog = new THREE.Fog(0x0a1020, 40, 160);

  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 300);
  const hemi = new THREE.HemisphereLight(0x9ad0ff, 0x1a1020, 0.85);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffffff, 1.1);
  sun.position.set(20, 40, 10);
  scene.add(sun);

  // Track
  const track = new THREE.Mesh(
    new THREE.BoxGeometry(18, 0.4, 220),
    new THREE.MeshStandardMaterial({ color: 0x2a3348, roughness: 0.9 })
  );
  track.position.y = -0.2;
  scene.add(track);
  const stripeMat = new THREE.MeshBasicMaterial({ color: 0xf5c542 });
  for (let z = -100; z <= 100; z += 12) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.05, 4), stripeMat);
    s.position.set(0, 0.02, z);
    scene.add(s);
  }
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x7a5cff, emissive: 0x221144 });
  [-9.5, 9.5].forEach((x) => {
    const w = new THREE.Mesh(new THREE.BoxGeometry(0.6, 1.2, 220), wallMat);
    w.position.set(x, 0.4, 0);
    scene.add(w);
  });
  const finish = new THREE.Mesh(
    new THREE.BoxGeometry(18, 0.15, 2),
    new THREE.MeshStandardMaterial({ color: 0x5ad0ff, emissive: 0x113355 })
  );
  finish.position.set(0, 0.05, -95);
  scene.add(finish);

  function makeCar(color, x, z) {
    const g = new THREE.Group();
    const body = new THREE.Mesh(
      new THREE.BoxGeometry(1.6, 0.5, 3.2),
      new THREE.MeshStandardMaterial({ color, metalness: 0.3, roughness: 0.45 })
    );
    body.position.y = 0.45;
    g.add(body);
    const cabin = new THREE.Mesh(
      new THREE.BoxGeometry(1.2, 0.45, 1.4),
      new THREE.MeshStandardMaterial({ color: 0x111822 })
    );
    cabin.position.set(0, 0.85, -0.2);
    g.add(cabin);
    g.position.set(x, 0, z);
    scene.add(g);
    return g;
  }

  const player = makeCar(0x3dd6c6, 0, 90);
  const rivals = [
    makeCar(0xff6b6b, -3.5, 70),
    makeCar(0xffb347, 3.5, 55),
    makeCar(0xc44dff, -2, 35),
  ];

  const keys = new Set();
  addEventListener("keydown", (e) => { keys.add(e.key.toLowerCase()); canvas.focus(); });
  addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  canvas.addEventListener("pointerdown", () => canvas.focus());

  let speed = 0;
  let boost = 0;
  let distance = 0;
  let alive = true;
  let won = false;
  const clock = new THREE.Clock();

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize);
  resize();

  function endGame(text, ok) {
    alive = false;
    won = ok;
    overlayText.textContent = text;
    overlay.classList.remove("hidden");
    statusEl.textContent = ok ? "Финиш!" : "Столкновение";
  }

  function reset() {
    player.position.set(0, 0, 90);
    player.rotation.y = 0;
    rivals[0].position.set(-3.5, 0, 70);
    rivals[1].position.set(3.5, 0, 55);
    rivals[2].position.set(-2, 0, 35);
    speed = 0; boost = 0; distance = 0; alive = true; won = false;
    overlay.classList.add("hidden");
    statusEl.textContent = "Гонка";
    scoreEl.textContent = "0 м";
  }
  restartBtn.addEventListener("click", reset);

  function collide(a, b, r = 2.2) {
    return a.position.distanceTo(b.position) < r;
  }

  function tick() {
    requestAnimationFrame(tick);
    const dt = Math.min(clock.getDelta(), 0.05);
    if (!alive) {
      renderer.render(scene, camera);
      return;
    }
    const left = keys.has("a") || keys.has("arrowleft");
    const right = keys.has("d") || keys.has("arrowright");
    const accel = keys.has("w") || keys.has("arrowup");
    const brake = keys.has("s") || keys.has("arrowdown");
    if (keys.has("shift")) boost = Math.min(1, boost + dt);
    else boost = Math.max(0, boost - dt * 0.5);

    const target = (accel ? 42 : 0) + boost * 28 - (brake ? 18 : 0);
    speed += (target - speed) * Math.min(1, dt * 2.5);
    if (left) player.position.x -= 14 * dt;
    if (right) player.position.x += 14 * dt;
    player.position.x = Math.max(-7.5, Math.min(7.5, player.position.x));
    player.position.z -= speed * dt;
    distance += speed * dt;
    scoreEl.textContent = Math.floor(distance) + " м · boost " + Math.round(boost * 100) + "%";
    statusEl.textContent = "WASD · Shift ускорение · до финиша " + Math.max(0, Math.floor(player.position.z + 95)) + " м";

    rivals.forEach((r, i) => {
      r.position.z -= (28 + i * 4) * dt;
      r.position.x += Math.sin(performance.now() / 700 + i) * 0.02;
      if (collide(player, r)) endGame("Столкновение с соперником", false);
    });
    if (Math.abs(player.position.x) > 8.2) endGame("Вылет с трассы", false);
    if (player.position.z <= -95) endGame("Финиш! Дистанция " + Math.floor(distance) + " м", true);

    camera.position.lerp(
      new THREE.Vector3(player.position.x * 0.35, 6, player.position.z + 12),
      0.12
    );
    camera.lookAt(player.position.x, 1, player.position.z - 8);
    renderer.render(scene, camera);
  }
  reset();
  tick();
  window.parent && window.parent.postMessage({ type: "nexa-game", event: "ready", genre: "racing" }, "*");
})();
"""


def files_for_three_racing() -> dict[str, str]:
    return {
        "index.html": index_html(
            title="NEXA Racing 3D",
            subtitle="WASD / стрелки — руль · Shift — ускорение · доедь до финиша",
            hud_extra='<span id="hint">3D</span>',
        ),
        "style.css": STYLE_CSS,
        "main.js": MAIN_JS,
        "scene.json": scene_json(
            genre="racing",
            objects=[
                {"id": "track", "type": "mesh", "role": "ground"},
                {"id": "player", "type": "car", "controllable": True},
                {"id": "rival-1", "type": "car", "ai": True},
                {"id": "rival-2", "type": "car", "ai": True},
                {"id": "rival-3", "type": "car", "ai": True},
                {"id": "finish", "type": "trigger", "role": "goal"},
            ],
        ),
        "README.md": "# NEXA Racing 3D\n\nThree.js CDN race. Controls: WASD/arrows, Shift boost.\n",
    }

"""Playable Three.js tank battle (CDN) — Part 13."""
from __future__ import annotations

from app.build.templates.three_common import STYLE_CSS, index_html, scene_json

MAIN_JS = r"""(() => {
  if (typeof THREE === "undefined") return;
  const canvas = document.getElementById("game");
  const statusEl = document.getElementById("status");
  const scoreEl = document.getElementById("score");
  const overlay = document.getElementById("overlay");
  const overlayText = document.getElementById("overlay-text");
  const restartBtn = document.getElementById("restart");

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1810);
  scene.fog = new THREE.Fog(0x1a1810, 30, 120);
  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
  scene.add(new THREE.HemisphereLight(0xffe6c0, 0x222211, 0.9));
  const sun = new THREE.DirectionalLight(0xffffff, 1);
  sun.position.set(30, 50, 10);
  scene.add(sun);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(120, 120),
    new THREE.MeshStandardMaterial({ color: 0x5a4a32, roughness: 1 })
  );
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  function tank(color, x, z) {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.9, 3.2), new THREE.MeshStandardMaterial({ color }));
    body.position.y = 0.55;
    g.add(body);
    const turret = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.55, 12), new THREE.MeshStandardMaterial({ color: 0x333333 }));
    turret.position.y = 1.2;
    g.add(turret);
    const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 2.2, 8), new THREE.MeshStandardMaterial({ color: 0x222222 }));
    barrel.rotation.z = Math.PI / 2;
    barrel.position.set(1.1, 1.2, 0);
    g.add(barrel);
    g.position.set(x, 0, z);
    scene.add(g);
    return { group: g, hp: 3, turret, barrel };
  }

  const player = tank(0x6bcf6b, 0, 20);
  const enemies = [tank(0xc44, -15, -10), tank(0xc44, 12, -18), tank(0xc44, 0, -28)];
  const shots = [];

  const keys = new Set();
  addEventListener("keydown", (e) => {
    keys.add(e.key.toLowerCase());
    if (e.key === " " || e.code === "Space") { e.preventDefault(); fire(); }
  });
  addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  canvas.addEventListener("pointerdown", () => canvas.focus());

  let score = 0;
  let alive = true;
  let cooldown = 0;
  const clock = new THREE.Clock();

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize);
  resize();

  function fire() {
    if (!alive || cooldown > 0) return;
    cooldown = 0.45;
    const dir = new THREE.Vector3(Math.sin(player.group.rotation.y), 0, -Math.cos(player.group.rotation.y));
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.18, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffee88 }));
    mesh.position.copy(player.group.position).add(new THREE.Vector3(0, 1.2, 0)).add(dir.clone().multiplyScalar(2));
    scene.add(mesh);
    shots.push({ mesh, dir, life: 2.2, fromPlayer: true });
  }

  function endGame(msg) {
    alive = false;
    overlayText.textContent = msg;
    overlay.classList.remove("hidden");
  }
  function reset() {
    player.group.position.set(0, 0, 20);
    player.group.rotation.y = 0;
    player.hp = 3;
    enemies.forEach((e, i) => {
      e.hp = 3;
      e.group.visible = true;
      e.group.position.set([-15, 12, 0][i], 0, [-10, -18, -28][i]);
    });
    shots.splice(0).forEach((s) => scene.remove(s.mesh));
    score = 0; alive = true; cooldown = 0;
    overlay.classList.add("hidden");
    scoreEl.textContent = "Уничтожено: 0/3";
  }
  restartBtn.addEventListener("click", reset);

  function tick() {
    requestAnimationFrame(tick);
    const dt = Math.min(clock.getDelta(), 0.05);
    cooldown = Math.max(0, cooldown - dt);
    if (alive) {
      const turn = (keys.has("a") || keys.has("arrowleft") ? 1 : 0) - (keys.has("d") || keys.has("arrowright") ? 1 : 0);
      player.group.rotation.y += turn * 1.8 * dt;
      const forward = (keys.has("w") || keys.has("arrowup") ? 1 : 0) - (keys.has("s") || keys.has("arrowdown") ? 1 : 0);
      player.group.position.x += Math.sin(player.group.rotation.y) * forward * 12 * dt;
      player.group.position.z -= Math.cos(player.group.rotation.y) * forward * 12 * dt;
      player.group.position.x = THREE.MathUtils.clamp(player.group.position.x, -50, 50);
      player.group.position.z = THREE.MathUtils.clamp(player.group.position.z, -50, 50);

      enemies.forEach((e) => {
        if (e.hp <= 0) return;
        const to = player.group.position.clone().sub(e.group.position);
        const ang = Math.atan2(to.x, -to.z);
        e.group.rotation.y = THREE.MathUtils.lerp(e.group.rotation.y, ang, 0.03);
        e.group.position.x += Math.sin(e.group.rotation.y) * 4 * dt;
        e.group.position.z -= Math.cos(e.group.rotation.y) * 4 * dt;
        if (Math.random() < 0.01) {
          const dir = new THREE.Vector3(Math.sin(e.group.rotation.y), 0, -Math.cos(e.group.rotation.y));
          const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.16, 8, 8), new THREE.MeshBasicMaterial({ color: 0xff6644 }));
          mesh.position.copy(e.group.position).add(new THREE.Vector3(0, 1.2, 0)).add(dir.clone().multiplyScalar(2));
          scene.add(mesh);
          shots.push({ mesh, dir, life: 2, fromPlayer: false });
        }
      });

      for (let i = shots.length - 1; i >= 0; i--) {
        const s = shots[i];
        s.mesh.position.addScaledVector(s.dir, 42 * dt);
        s.life -= dt;
        let hit = false;
        if (s.fromPlayer) {
          enemies.forEach((e) => {
            if (e.hp > 0 && s.mesh.position.distanceTo(e.group.position) < 2) {
              e.hp -= 1; hit = true;
              if (e.hp <= 0) { e.group.visible = false; score += 1; scoreEl.textContent = "Уничтожено: " + score + "/3"; }
            }
          });
        } else if (s.mesh.position.distanceTo(player.group.position) < 2) {
          player.hp -= 1; hit = true;
          if (player.hp <= 0) endGame("Танк подбит");
        }
        if (hit || s.life <= 0) { scene.remove(s.mesh); shots.splice(i, 1); }
      }
      if (score >= 3) endGame("Победа! Все цели уничтожены");
      statusEl.textContent = "HP " + player.hp + " · WASD езда · Пробел выстрел";
    }
    camera.position.set(player.group.position.x - Math.sin(player.group.rotation.y) * 12, 10, player.group.position.z + Math.cos(player.group.rotation.y) * 12);
    camera.lookAt(player.group.position.x, 1, player.group.position.z);
    renderer.render(scene, camera);
  }
  reset();
  tick();
  window.parent && window.parent.postMessage({ type: "nexa-game", event: "ready", genre: "tank" }, "*");
})();
"""


def files_for_three_tank() -> dict[str, str]:
    return {
        "index.html": index_html(
            title="NEXA Tank 3D",
            subtitle="WASD — движение · Пробел — выстрел · уничтожь 3 цели",
        ),
        "style.css": STYLE_CSS,
        "main.js": MAIN_JS,
        "scene.json": scene_json(
            genre="tank",
            objects=[
                {"id": "player", "type": "tank", "controllable": True},
                {"id": "enemy-1", "type": "tank", "ai": True},
                {"id": "enemy-2", "type": "tank", "ai": True},
                {"id": "enemy-3", "type": "tank", "ai": True},
            ],
        ),
        "README.md": "# NEXA Tank 3D\n\nDestroy 3 enemy tanks. WASD + Space.\n",
    }

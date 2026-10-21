"""Playable Three.js adventure (CDN) — Part 13."""
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
  scene.background = new THREE.Color(0x0e1a24);
  scene.fog = new THREE.Fog(0x0e1a24, 25, 90);
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 200);
  scene.add(new THREE.HemisphereLight(0xb0d8ff, 0x223322, 0.95));
  const sun = new THREE.DirectionalLight(0xffffff, 1);
  sun.position.set(20, 40, 10);
  scene.add(sun);

  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(40, 48),
    new THREE.MeshStandardMaterial({ color: 0x2f5d3a, roughness: 1 })
  );
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  const hero = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.45, 1.1, 4, 8),
    new THREE.MeshStandardMaterial({ color: 0x7a5cff })
  );
  hero.position.set(0, 1.1, 12);
  scene.add(hero);

  const gems = [];
  for (let i = 0; i < 6; i++) {
    const gem = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.45),
      new THREE.MeshStandardMaterial({ color: 0x5ad0ff, emissive: 0x113344, metalness: 0.6 })
    );
    const a = (i / 6) * Math.PI * 2;
    gem.position.set(Math.cos(a) * 14, 0.7, Math.sin(a) * 14 - 4);
    scene.add(gem);
    gems.push({ mesh: gem, taken: false });
  }
  const portal = new THREE.Mesh(
    new THREE.TorusGeometry(2.2, 0.25, 12, 32),
    new THREE.MeshStandardMaterial({ color: 0xc44dff, emissive: 0x440066 })
  );
  portal.position.set(0, 2, -18);
  scene.add(portal);
  const rock = new THREE.Mesh(
    new THREE.DodecahedronGeometry(2.5),
    new THREE.MeshStandardMaterial({ color: 0x666666 })
  );
  rock.position.set(8, 1.2, 0);
  scene.add(rock);

  const keys = new Set();
  addEventListener("keydown", (e) => keys.add(e.key.toLowerCase()));
  addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  canvas.addEventListener("pointerdown", () => canvas.focus());

  let score = 0;
  let alive = true;
  const clock = new THREE.Clock();
  const facing = new THREE.Vector3(0, 0, -1);

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize);
  resize();

  function endGame(msg) {
    alive = false;
    overlayText.textContent = msg;
    overlay.classList.remove("hidden");
  }
  function reset() {
    hero.position.set(0, 1.1, 12);
    gems.forEach((g) => { g.taken = false; g.mesh.visible = true; });
    score = 0; alive = true;
    overlay.classList.add("hidden");
    scoreEl.textContent = "Кристаллы: 0/6";
  }
  restartBtn.addEventListener("click", reset);

  function tick() {
    requestAnimationFrame(tick);
    const dt = Math.min(clock.getDelta(), 0.05);
    if (alive) {
      const move = new THREE.Vector3(
        (keys.has("d") || keys.has("arrowright") ? 1 : 0) - (keys.has("a") || keys.has("arrowleft") ? 1 : 0),
        0,
        (keys.has("s") || keys.has("arrowdown") ? 1 : 0) - (keys.has("w") || keys.has("arrowup") ? 1 : 0)
      );
      if (move.lengthSq() > 0) {
        move.normalize();
        facing.copy(move);
        hero.position.addScaledVector(move, 8 * dt);
        hero.rotation.y = Math.atan2(move.x, move.z);
      }
      // collide rock
      if (hero.position.distanceTo(rock.position) < 3.2) {
        const push = hero.position.clone().sub(rock.position).setY(0).normalize();
        hero.position.addScaledVector(push, 0.2);
      }
      const r = Math.hypot(hero.position.x, hero.position.z);
      if (r > 38) {
        hero.position.multiplyScalar(38 / r);
      }
      gems.forEach((g) => {
        g.mesh.rotation.y += dt;
        if (!g.taken && hero.position.distanceTo(g.mesh.position) < 1.4) {
          g.taken = true; g.mesh.visible = false; score += 1;
          scoreEl.textContent = "Кристаллы: " + score + "/6";
        }
      });
      portal.rotation.y += dt * 0.8;
      if (score >= 6 && hero.position.distanceTo(portal.position) < 2.8) {
        endGame("Приключение завершено!");
      }
      statusEl.textContent = score >= 6 ? "Иди к порталу" : "Собери кристаллы · WASD";
    }
    camera.position.lerp(new THREE.Vector3(hero.position.x - facing.x * 8, 7, hero.position.z - facing.z * 8), 0.1);
    camera.lookAt(hero.position.x, 1.2, hero.position.z);
    renderer.render(scene, camera);
  }
  reset();
  tick();
  window.parent && window.parent.postMessage({ type: "nexa-game", event: "ready", genre: "adventure" }, "*");
})();
"""


def files_for_three_adventure() -> dict[str, str]:
    return {
        "index.html": index_html(
            title="NEXA Adventure 3D",
            subtitle="WASD — ходьба · собери 6 кристаллов и войди в портал",
        ),
        "style.css": STYLE_CSS,
        "main.js": MAIN_JS,
        "scene.json": scene_json(
            genre="adventure",
            objects=[
                {"id": "hero", "type": "character", "controllable": True},
                {"id": "gems", "type": "collectible", "count": 6},
                {"id": "portal", "type": "goal"},
                {"id": "rock", "type": "obstacle"},
            ],
        ),
        "README.md": "# NEXA Adventure 3D\n\nCollect gems and reach the portal.\n",
    }

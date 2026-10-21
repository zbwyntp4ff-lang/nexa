"""Playable Three.js flight sim (CDN) — Part 13."""
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
  scene.background = new THREE.Color(0x87b7ff);
  scene.fog = new THREE.Fog(0x87b7ff, 80, 400);
  const camera = new THREE.PerspectiveCamera(70, 1, 0.1, 800);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1));
  const sun = new THREE.DirectionalLight(0xfff2cc, 1.2);
  sun.position.set(50, 80, 20);
  scene.add(sun);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(800, 800),
    new THREE.MeshStandardMaterial({ color: 0x3d7a4a, roughness: 1 })
  );
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);
  for (let i = 0; i < 40; i++) {
    const tree = new THREE.Mesh(
      new THREE.ConeGeometry(2 + Math.random(), 8 + Math.random() * 6, 6),
      new THREE.MeshStandardMaterial({ color: 0x2f6b3a })
    );
    tree.position.set((Math.random() - 0.5) * 500, 4, (Math.random() - 0.5) * 500);
    scene.add(tree);
  }
  const rings = [];
  for (let i = 0; i < 8; i++) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(6, 0.5, 8, 24),
      new THREE.MeshStandardMaterial({ color: 0xffd34e, emissive: 0x553300 })
    );
    ring.position.set((i % 2 ? -20 : 20), 18 + i * 3, -40 - i * 35);
    ring.rotation.y = Math.PI / 2;
    scene.add(ring);
    rings.push({ mesh: ring, taken: false });
  }

  const plane = new THREE.Group();
  const fuselage = new THREE.Mesh(
    new THREE.BoxGeometry(1.2, 0.8, 4),
    new THREE.MeshStandardMaterial({ color: 0xeeeeee, metalness: 0.4 })
  );
  plane.add(fuselage);
  const wing = new THREE.Mesh(
    new THREE.BoxGeometry(6, 0.15, 1.2),
    new THREE.MeshStandardMaterial({ color: 0x5ad0ff })
  );
  plane.add(wing);
  plane.position.set(0, 25, 40);
  scene.add(plane);

  const keys = new Set();
  addEventListener("keydown", (e) => keys.add(e.key.toLowerCase()));
  addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  canvas.addEventListener("pointerdown", () => canvas.focus());

  let speed = 28;
  let score = 0;
  let alive = true;
  const clock = new THREE.Clock();
  const velocity = new THREE.Vector3();

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
    plane.position.set(0, 25, 40);
    plane.rotation.set(0, 0, 0);
    speed = 28; score = 0; alive = true;
    rings.forEach((r) => { r.taken = false; r.mesh.visible = true; });
    overlay.classList.add("hidden");
    scoreEl.textContent = "Кольца: 0/8";
  }
  restartBtn.addEventListener("click", reset);

  function tick() {
    requestAnimationFrame(tick);
    const dt = Math.min(clock.getDelta(), 0.05);
    if (alive) {
      if (keys.has("w") || keys.has("arrowup")) plane.rotation.x -= 0.9 * dt;
      if (keys.has("s") || keys.has("arrowdown")) plane.rotation.x += 0.9 * dt;
      if (keys.has("a") || keys.has("arrowleft")) plane.rotation.z += 1.2 * dt;
      if (keys.has("d") || keys.has("arrowright")) plane.rotation.z -= 1.2 * dt;
      if (keys.has("shift")) speed = Math.min(60, speed + 20 * dt);
      else speed = Math.max(18, speed - 8 * dt);
      plane.rotation.x = THREE.MathUtils.clamp(plane.rotation.x, -0.7, 0.7);
      plane.rotation.z = THREE.MathUtils.clamp(plane.rotation.z, -0.8, 0.8);
      velocity.set(0, 0, -1).applyEuler(plane.rotation).multiplyScalar(speed * dt);
      plane.position.add(velocity);
      if (plane.position.y < 2) endGame("Крушение. Кольца: " + score);
      rings.forEach((r) => {
        if (!r.taken && plane.position.distanceTo(r.mesh.position) < 8) {
          r.taken = true; r.mesh.visible = false; score += 1;
          scoreEl.textContent = "Кольца: " + score + "/8";
          if (score >= 8) endGame("Маршрут пройден!");
        }
      });
      statusEl.textContent = "Высота " + Math.floor(plane.position.y) + " · скорость " + Math.floor(speed);
    }
    const back = new THREE.Vector3(0, 4, 14).applyEuler(plane.rotation);
    camera.position.copy(plane.position).add(back);
    camera.lookAt(plane.position);
    renderer.render(scene, camera);
  }
  reset();
  tick();
  window.parent && window.parent.postMessage({ type: "nexa-game", event: "ready", genre: "flight" }, "*");
})();
"""


def files_for_three_flight() -> dict[str, str]:
    return {
        "index.html": index_html(
            title="NEXA Flight 3D",
            subtitle="WASD — тангаж/крен · Shift — газ · пролети сквозь кольца",
        ),
        "style.css": STYLE_CSS,
        "main.js": MAIN_JS,
        "scene.json": scene_json(
            genre="flight",
            objects=[
                {"id": "ground", "type": "plane"},
                {"id": "plane", "type": "aircraft", "controllable": True},
                {"id": "rings", "type": "collectible", "count": 8},
            ],
        ),
        "README.md": "# NEXA Flight 3D\n\nFly through rings. WASD + Shift.\n",
    }

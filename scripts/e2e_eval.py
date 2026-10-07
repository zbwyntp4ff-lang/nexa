import json
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8420"


def post_run(msg: str, cid: str) -> dict:
    req = urllib.request.Request(
        API + "/api/v1/build/run",
        data=json.dumps({"message": msg, "conversation_id": cid}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def get(path: str) -> tuple[int, int]:
    with urllib.request.urlopen(API + path, timeout=20) as r:
        return r.status, len(r.read())


r1 = post_run("Создай игру, где машина собирает монеты", "e2e-eval-1")
print(
    "T1",
    r1["success"],
    r1.get("status"),
    r1.get("evaluation", {}).get("status"),
    r1.get("evaluation", {}).get("score"),
    "improve",
    r1.get("improvement_attempts"),
)
assert r1["success"] and r1["status"] == "READY" and r1["evaluation"]["status"] == "PASS"
js = Path(r1["root_path"]).joinpath("main.js").read_text(encoding="utf-8")
assert "car" in js and "coins" in js
st, _ = get(r1["preview_url"])
assert st == 200
assert r1.get("improvement_attempts", 0) == 0

r2 = post_run("Создай игру с машиной, монетами и врагами", "e2e-eval-2")
print(
    "T2",
    r2["success"],
    r2.get("status"),
    r2.get("evaluation", {}).get("status"),
    r2.get("evaluation", {}).get("score"),
    "improve",
    r2.get("improvement_attempts"),
)
assert r2["success"] and r2["evaluation"]["status"] == "PASS"
js2 = Path(r2["root_path"]).joinpath("main.js").read_text(encoding="utf-8")
assert "car" in js2 and "coins" in js2 and "__NEXA_ENEMIES__" in js2
assert r2.get("improvement_attempts", 0) >= 1
st2, _ = get(r2["preview_url"])
assert st2 == 200

url = f"{API}/api/v1/build/events?project_id={r2['project_id']}&limit=100"
with urllib.request.urlopen(url) as r:
    ev = json.loads(r.read().decode())
types = {e["type"] for e in ev["events"]}
print("events", sorted(types))
assert "EVALUATION_STARTED" in types
assert "EVALUATION_COMPLETED" in types
assert "IMPROVEMENT_STARTED" in types
print("E2E_EVAL_OK")

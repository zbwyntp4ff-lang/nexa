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
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def get(path: str) -> tuple[int, int]:
    with urllib.request.urlopen(API + path, timeout=20) as r:
        return r.status, len(r.read())


def check(label: str, body: dict) -> None:
    ev = body.get("evaluation") or {}
    rt = ev.get("runtime") or {}
    print(
        label,
        "success=",
        body.get("success"),
        "status=",
        body.get("status"),
        "eval=",
        ev.get("status"),
        ev.get("score"),
        "runtime=",
        rt.get("runtimeVerification"),
        "http=",
        rt.get("previewHttpStatus"),
        "browser=",
        rt.get("browserInstrumentation"),
    )
    assert body["success"] and body["status"] == "READY"
    assert ev.get("status") == "PASS"
    # Prefer real browser when Playwright is available; otherwise honest HTTP fallback
    mode = rt.get("runtimeVerification")
    assert mode in {"HTTP_PREVIEW", "BROWSER_PREVIEW"}
    if mode == "BROWSER_PREVIEW":
        assert rt.get("browserInstrumentation") == "PLAYWRIGHT"
        assert rt.get("browserAvailable") is True
        assert rt.get("pageLoaded") is True
    else:
        assert rt.get("browserInstrumentation") == "NOT_AVAILABLE"
    assert rt.get("previewHttpStatus") == 200
    assert rt.get("htmlLoaded") is True
    st, _ = get(body["preview_url"])
    assert st == 200
    js = Path(body["root_path"]).joinpath("main.js").read_text(encoding="utf-8")
    assert "car" in js and "coins" in js


r1 = post_run("Создай игру, где машина собирает монеты", "e2e-rt-1")
check("T1", r1)
assert r1.get("improvement_attempts", 0) == 0

r2 = post_run(
    "Создай игру, где машина собирает монеты и избегает врагов",
    "e2e-rt-2",
)
check("T2", r2)
js2 = Path(r2["root_path"]).joinpath("main.js").read_text(encoding="utf-8")
assert "__NEXA_ENEMIES__" in js2
assert r2.get("improvement_attempts", 0) >= 1

url = f"{API}/api/v1/build/events?project_id={r2['project_id']}&limit=100"
with urllib.request.urlopen(url) as r:
    types = {e["type"] for e in json.loads(r.read().decode())["events"]}
print("events", sorted(types))
assert "RUNTIME_VERIFICATION_STARTED" in types
assert "RUNTIME_VERIFICATION_COMPLETED" in types
assert "EVALUATION_COMPLETED" in types
print("E2E_RUNTIME_OK")

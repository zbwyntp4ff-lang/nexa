import time
from pathlib import Path
import os
import httpx

png = Path(os.environ["TEMP"]) / "nexa_i2v_test.png"
files = {"file": ("nexa_i2v_test.png", png.read_bytes(), "image/png")}
r = httpx.post("http://127.0.0.1:8420/api/v1/attachments", files=files, timeout=30)
r.raise_for_status()
att = r.json()
print("att", att["id"], att["status"])
body = {"prompt": "оживи", "attachment_ids": [att["id"]], "force": True}
jr = httpx.post("http://127.0.0.1:8420/api/v1/video/image-to-video", json=body, timeout=30)
print("start", jr.status_code, jr.text[:800])
job = jr.json()
jid = job.get("job_id")
for _ in range(20):
    time.sleep(0.7)
    s = httpx.get(f"http://127.0.0.1:8420/api/v1/video/jobs/{jid}", timeout=30).json()
    print("poll", s.get("phase"), s.get("progress"), s.get("error") or s.get("message"))
    if s.get("phase") in ("ready", "failed"):
        break

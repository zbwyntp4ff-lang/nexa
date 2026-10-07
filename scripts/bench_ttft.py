"""Quick stream TTFT benchmark against a running NEXA backend."""
from __future__ import annotations

import json
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8420"


def measure(prompt: str) -> None:
    t0 = time.perf_counter()
    first = None
    text = ""
    done: dict = {}
    with httpx.stream(
        "POST",
        f"{BASE}/api/v1/chat/stream",
        json={"message": prompt, "history": []},
        timeout=180,
    ) as response:
        headers_at = time.perf_counter()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:].strip())
            if event.get("type") == "delta" and event.get("text"):
                if first is None:
                    first = time.perf_counter()
                text += event["text"]
            if event.get("type") == "done":
                done = event
                break
    t1 = time.perf_counter()
    client_ttft = ((first - t0) * 1000) if first else None
    print("===", prompt)
    print(
        "  headers_ms={:.0f} client_ttft_ms={} server_ttft={} total_ms={:.0f} "
        "server_total={} model={} chars={}".format(
            (headers_at - t0) * 1000,
            f"{client_ttft:.0f}" if client_ttft is not None else "none",
            done.get("ttft_ms"),
            (t1 - t0) * 1000,
            done.get("total_ms"),
            done.get("model"),
            len(text),
        )
    )
    print(" ", repr(text[:200].replace("\n", " | ")))


def main() -> None:
    httpx.put(
        f"{BASE}/api/v1/models/selection",
        json={"provider": "ollama", "model": "qwen2.5:1.5b", "allow_fallback": True},
        timeout=30,
    )
    prompts = [
        "Привет",
        "Что такое NEXA?",
        "Объясни искусственный интеллект простыми словами",
        "Придумай 5 идей для проекта",
    ]
    for prompt in prompts:
        measure(prompt)
        print()


if __name__ == "__main__":
    main()

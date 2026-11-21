from pathlib import Path


def test_production_uvicorn_trusts_forwarded_headers_only_from_local_proxy() -> None:
    script = Path("scripts/prod_start.sh").read_text(encoding="utf-8")
    assert "--proxy-headers --forwarded-allow-ips='127.0.0.1'" in script
    assert "--forwarded-allow-ips='*'" not in script


def test_guest_quota_does_not_read_user_supplied_forwarded_for_header() -> None:
    source = Path("app/beta/guest_quota.py").read_text(encoding="utf-8")
    assert "request.client.host" in source
    assert "request.headers" not in source.lower()

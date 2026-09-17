import pytest

from app.services.ssrf import InvalidFetchUrl, validate_fetch_url


def test_rejects_non_http_schemes(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ssrf._resolve", lambda host, port: [])
    with pytest.raises(InvalidFetchUrl):
        validate_fetch_url("file:///etc/passwd")
    with pytest.raises(InvalidFetchUrl):
        validate_fetch_url("ftp://example.com")


def test_rejects_localhost(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ssrf._resolve", lambda host, port: [])
    with pytest.raises(InvalidFetchUrl):
        validate_fetch_url("http://localhost:6333")


def test_rejects_private_ip_target(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ssrf._resolve", lambda host, port: ["10.0.0.5"])
    with pytest.raises(InvalidFetchUrl):
        validate_fetch_url("http://internal.host/x")


def test_rejects_cloud_metadata_ip(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ssrf._resolve", lambda host, port: ["169.254.169.254"])
    with pytest.raises(InvalidFetchUrl):
        validate_fetch_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_ipv4_mapped_private(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ssrf._resolve", lambda host, port: ["192.168.1.1"])
    with pytest.raises(InvalidFetchUrl):
        validate_fetch_url("http://anything.example")


def test_allows_public_https(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ssrf._resolve", lambda host, port: ["93.184.216.34"])
    validate_fetch_url("https://example.com/x")
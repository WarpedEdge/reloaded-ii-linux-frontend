import io
import ssl
from urllib.error import HTTPError, URLError

import pytest

from reloaded_linux_manager import network, releases, updater


def test_bundled_roots_work_without_host_ca_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing.pem"))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "missing-certs"))
    context = network.ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.cert_store_stats()["x509_ca"] > 0


def test_host_trust_is_loaded_before_bundled_roots(monkeypatch):
    calls = []

    class Context:
        def load_verify_locations(self, **kwargs):
            calls.append(kwargs)

    def create():
        calls.append("host defaults")
        return Context()

    monkeypatch.setattr(network.ssl, "create_default_context", create)
    network.ssl_context()
    assert calls == ["host defaults", {"cafile": network.certifi.where()}]


def test_release_and_update_download_requests_use_verified_context(monkeypatch):
    requests = []

    def open_url(request, **kwargs):
        requests.append((request.full_url, kwargs))
        return io.BytesIO(b"response")

    monkeypatch.setattr(network, "urlopen", open_url)
    for request in (releases.request, updater.request):
        with request("https://github.com/") as response:
            assert response.read() == b"response"
    assert len(requests) == 2
    for url, kwargs in requests:
        assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["context"].check_hostname
        assert kwargs["timeout"] > 0


def test_certificate_failure_is_not_retried_without_verification(monkeypatch):
    calls = []

    def failing(*args, **kwargs):
        calls.append(kwargs)
        raise URLError(ssl.SSLCertVerificationError(1, "untrusted test certificate"))

    monkeypatch.setattr(network, "urlopen", failing)
    with pytest.raises(RuntimeError, match="Certificate verification remains enabled"):
        releases.request("https://github.com/")
    assert len(calls) == 1
    assert calls[0]["context"].verify_mode == ssl.CERT_REQUIRED


def test_http_and_other_network_errors_keep_existing_handling(monkeypatch):
    for error in (HTTPError("https://github.com/", 403, "rate limited", {}, None), URLError("offline")):

        def failing(*args, **kwargs):
            raise error

        monkeypatch.setattr(network, "urlopen", failing)
        with pytest.raises(type(error)) as raised:
            network.open_url("https://github.com/", timeout=1)
        assert raised.value is error

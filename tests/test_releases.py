import io
import json
from urllib.error import HTTPError

import pytest

from reloaded_linux_manager import releases


def test_metadata_cache_allows_repeated_setup_and_rate_limit_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    data = {"tag_name": "1.31.0", "assets": [{"name": name} for name in ("Release.zip", "Setup-Linux.exe")]}
    calls = []

    def request(url):
        calls.append(url)
        if len(calls) > 1:
            raise HTTPError(url, 403, "limited", {"X-RateLimit-Remaining": "0"}, None)
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(releases, "request", request)
    monkeypatch.setattr(releases.time, "time", lambda: 10000)
    assert releases.release()[0] == "1.31.0"
    assert releases.release()[0] == "1.31.0"
    assert len(calls) == 1
    monkeypatch.setattr(releases.time, "time", lambda: 20000)
    assert releases.release()[0] == "1.31.0"
    assert len(calls) == 2
    # A different requested version must not silently reuse the cached latest release.
    with pytest.raises(RuntimeError, match="API rate limit"):
        releases.release("1.30.0")


def test_rate_limit_without_metadata_explains_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def request(url):
        raise HTTPError(url, 429, "limited", {"Retry-After": "120"}, None)

    monkeypatch.setattr(releases, "request", request)
    with pytest.raises(RuntimeError, match="Try again in 120 seconds"):
        releases.release()

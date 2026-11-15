"""Verified HTTPS with bundled public roots for hosts using different CA paths."""

import ssl
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi


def ssl_context():
    # Keep host trust and explicit SSL_CERT_FILE/SSL_CERT_DIR settings, then add portable roots.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


def open_url(request, timeout):
    try:
        return urlopen(request, timeout=timeout, context=ssl_context())
    except URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                "HTTPS certificate verification failed. The app includes trusted public certificates, "
                "but this connection could not be verified. Check the system date and any network "
                "proxy or custom certificate settings. Certificate verification remains enabled. "
                "Details: " + str(exc.reason)
            ) from exc
        raise


def check_https():
    """Exercise the same certificate handling as downloads without looking up a release."""
    request = Request("https://github.com/", headers={"User-Agent": "Reloaded-Linux-Manager/HTTPS-check"})
    with open_url(request, timeout=30) as response:
        response.read(1)
    return "Verified HTTPS connection to GitHub passed."

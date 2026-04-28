"""GitHub OAuth PKCE and token exchange with the Insighta backend."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    q = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": "read:user user:email",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(q)}"


def _parse_redirect_bind(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/callback"
    if not path.startswith("/"):
        path = "/" + path
    return host, port, path


def wait_for_oauth_callback(
    *,
    redirect_uri: str,
    expected_state: str,
    timeout_s: float = 600.0,
    open_browser: Callable[[str], None] | None = None,
    authorize_url: str,
) -> tuple[str | None, str | None]:
    """
    Start a local HTTP server, open the authorize URL, return (code, error_message).
    """
    host, port, callback_path = _parse_redirect_bind(redirect_uri)
    captured: dict[str, str | None] = {"code": None, "error": None, "state": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != callback_path:
                self.send_error(404, "Not Found")
                return
            qs = parse_qs(parsed.query)
            captured["code"] = (qs.get("code") or [None])[0]
            captured["state"] = (qs.get("state") or [None])[0]
            err = (qs.get("error") or [None])[0]
            if err:
                captured["error"] = err
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if err:
                body = (
                    f"<html><body><p>GitHub returned an error: {err!s}</p>"
                    "<p>You can close this tab.</p></body></html>"
                )
            else:
                body = (
                    "<html><body><p>Signed in. You can close this tab "
                    "and return to the terminal.</p></body></html>"
                )
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = HTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if open_browser:
            open_browser(authorize_url)
        else:
            webbrowser.open(authorize_url)

        remaining = timeout_s
        while remaining > 0:
            if captured["error"]:
                return None, str(captured["error"])
            code = captured["code"]
            st = captured["state"]
            if code and st:
                if st != expected_state:
                    return None, "OAuth state mismatch (possible CSRF)"
                return str(code), None
            time.sleep(0.25)
            remaining -= 0.25
        return None, "Timed out waiting for GitHub redirect"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)


def exchange_code_with_backend(
    *,
    api_base_url: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict:
    url = f"{api_base_url.rstrip('/')}/auth/github/cli"
    payload = {
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload)
    try:
        body = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from backend ({r.status_code})") from e
    if r.status_code >= 400:
        msg = body.get("message", r.text) if isinstance(body, dict) else r.text
        raise RuntimeError(msg or f"HTTP {r.status_code}")
    if not isinstance(body, dict) or body.get("status") != "success":
        raise RuntimeError(str(body))
    return body


def refresh_tokens(*, api_base_url: str, refresh_token: str) -> dict:
    url = f"{api_base_url.rstrip('/')}/auth/refresh"
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json={"refresh_token": refresh_token})
    try:
        body = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from backend ({r.status_code})") from e
    if r.status_code >= 400:
        msg = body.get("message", r.text) if isinstance(body, dict) else r.text
        raise RuntimeError(msg or f"HTTP {r.status_code}")
    if not isinstance(body, dict) or body.get("status") != "success":
        raise RuntimeError(str(body))
    return body


def logout_backend(*, api_base_url: str, refresh_token: str) -> None:
    url = f"{api_base_url.rstrip('/')}/auth/logout"
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json={"refresh_token": refresh_token})
    if r.status_code >= 400:
        try:
            body = r.json()
            msg = body.get("message", r.text) if isinstance(body, dict) else r.text
        except json.JSONDecodeError:
            msg = r.text
        raise RuntimeError(msg or f"HTTP {r.status_code}")

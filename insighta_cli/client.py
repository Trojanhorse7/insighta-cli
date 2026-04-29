"""HTTP client: API version header, bearer auth, refresh on 401."""

from __future__ import annotations

import json
from typing import Any

import httpx

from insighta_cli.auth import refresh_tokens
from insighta_cli.config import load_credentials, save_credentials

API_VERSION_HEADER = "X-API-Version"
API_VERSION = "1"


class InsightaApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class InsightaClient:
    def __init__(
        self,
        api_base_url: str,
        access_token: str,
        refresh_token: str,
        *,
        persist_refresh: bool = True,
    ) -> None:
        self.api_base_url = api_base_url.strip().rstrip("/")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._persist_refresh = persist_refresh

    @classmethod
    def from_credentials(cls, creds: dict) -> InsightaClient:
        api = str(creds.get("api_base_url", "")).strip().rstrip("/")
        access = str(creds.get("access_token", ""))
        refresh = str(creds.get("refresh_token", ""))
        if not api or not access or not refresh:
            raise InsightaApiError("Credentials missing; run `insighta login`")
        return cls(api, access, refresh, persist_refresh=True)

    def _persist_if_needed(self) -> None:
        if not self._persist_refresh:
            return
        existing = load_credentials()
        if not existing:
            return
        existing["access_token"] = self.access_token
        existing["refresh_token"] = self.refresh_token
        existing["api_base_url"] = self.api_base_url
        save_credentials(existing)

    def _headers(self, *, accept: str | None = None) -> dict[str, str]:
        return {
            API_VERSION_HEADER: API_VERSION,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": accept if accept is not None else "application/json",
        }

    def _do_refresh(self) -> None:
        try:
            data = refresh_tokens(
                api_base_url=self.api_base_url, refresh_token=self.refresh_token
            )
        except RuntimeError as e:
            raise InsightaApiError(
                str(e) or "Session expired; run `insighta login` again.",
                status_code=401,
            ) from None
        self.access_token = str(data["access_token"])
        self.refresh_token = str(data["refresh_token"])
        self._persist_if_needed()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        expect_json: bool = True,
    ) -> httpx.Response:
        url = f"{self.api_base_url}{path if path.startswith('/') else '/' + path}"
        accept = "application/json" if expect_json else "*/*"
        with httpx.Client(timeout=120.0) as http:
            r = http.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=self._headers(accept=accept),
            )
            if r.status_code == 401 and self.refresh_token:
                try:
                    self._do_refresh()
                except InsightaApiError:
                    raise
                r = http.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=self._headers(accept=accept),
                )

            if expect_json and r.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = r.json()
                except json.JSONDecodeError:
                    body = None
                if r.status_code >= 400:
                    msg = (
                        body.get("message", r.text)
                        if isinstance(body, dict)
                        else (r.text or f"HTTP {r.status_code}")
                    )
                    text = str(msg)
                    if r.status_code == 404:
                        text = f"{text} — {method} {url}"
                    raise InsightaApiError(text, status_code=r.status_code, body=body)
                return r

            if r.status_code >= 400:
                try:
                    body = r.json()
                    msg = body.get("message", r.text) if isinstance(body, dict) else r.text
                except json.JSONDecodeError:
                    msg = r.text
                text = str(msg or f"HTTP {r.status_code}")
                if r.status_code == 404:
                    text = f"{text} — {method} {url}"
                raise InsightaApiError(text, status_code=r.status_code)

            return r

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        r = self.request("GET", path, params=params)
        if not r.content:
            return None
        return r.json()

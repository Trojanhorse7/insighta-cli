"""Typer entrypoint for the Insighta CLI."""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.console import Console

from insighta_cli import __version__
from insighta_cli.auth import (
    build_authorize_url,
    exchange_code_with_backend,
    generate_pkce_pair,
    logout_backend,
    wait_for_oauth_callback,
)
from insighta_cli.client import InsightaApiError, InsightaClient
from insighta_cli.config import (
    api_github_callback_url,
    api_base_url_from_store_or_default,
    clear_credentials_file,
    default_api_base_url,
    default_github_client_id,
    default_oauth_redirect,
    load_credentials,
    save_credentials,
)

app = typer.Typer(
    no_args_is_help=True,
    help="Insighta Labs+ - profiles API CLI",
)
profiles_app = typer.Typer(help="List, search, CRUD, and export profiles")
app.add_typer(profiles_app, name="profiles")
console = Console(stderr=True)


def main() -> None:
    app()


def _decode_jwt_payload_unverified(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Access token is not a JWT")
    payload_b64 = parts[1]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    raw = base64.urlsafe_b64decode(padded)
    return json.loads(raw.decode("utf-8"))


def _exp_utc_str(exp_unix: int) -> str:
    return datetime.fromtimestamp(exp_unix, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _get_client() -> InsightaClient:
    creds = load_credentials()
    if not creds:
        console.print("[red]Not logged in. Run `insighta login`.[/red]")
        raise typer.Exit(1)
    try:
        return InsightaClient.from_credentials(creds)
    except InsightaApiError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _handle_api_err(e: InsightaApiError) -> None:
    console.print(f"[red]{e}[/red]")
    if e.status_code == 401:
        console.print("[dim]Try `insighta login` again.[/dim]")
    raise typer.Exit(1) from e


def _version_option(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_option,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """Insighta CLI root."""


@app.command()
def login(
    api_url: Annotated[
        Optional[str],
        typer.Option("--api-url", help="Insighta API base URL (stored in credentials)"),
    ] = None,
    github_client_id: Annotated[
        Optional[str],
        typer.Option("--github-client-id", help="GitHub OAuth App client ID (matches backend app)"),
    ] = None,
    redirect_uri: Annotated[
        Optional[str],
        typer.Option(
            "--redirect-uri",
            help="Local listener URL; must match INSIGHTA_CLI_OAUTH_REDIRECT on the API (not the GitHub app callback)",
        ),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option("--no-browser", help="Print the authorize URL instead of opening a browser"),
    ] = False,
) -> None:
    """Sign in with GitHub (opens a browser; stores tokens under ~/.insighta/)."""
    base = (api_url or default_api_base_url()).rstrip("/")
    cid = (github_client_id or default_github_client_id()).strip()
    if not cid:
        console.print(
            "[red]Set INSIGHTA_GITHUB_CLIENT_ID or pass --github-client-id "
            "(same value as GITHUB_CLIENT_ID on the API).[/red]"
        )
        raise typer.Exit(1)
    redir_listen = (redirect_uri or default_oauth_redirect()).strip()
    oauth_cb = api_github_callback_url(base)
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    auth_url = build_authorize_url(
        client_id=cid,
        redirect_uri=oauth_cb,
        state=state,
        code_challenge=challenge,
    )

    def _open(url: str) -> None:
        if no_browser:
            console.print("[cyan]Open this URL in your browser:[/cyan]")
            typer.echo(url)
            return
        import webbrowser

        webbrowser.open(url)

    code, err = wait_for_oauth_callback(
        redirect_uri=redir_listen,
        expected_state=state,
        authorize_url=auth_url,
        open_browser=_open,
    )
    if err or not code:
        console.print(f"[red]Login failed: {err or 'no code'}[/red]")
        raise typer.Exit(1)
    try:
        body = exchange_code_with_backend(
            api_base_url=base,
            code=code,
            code_verifier=verifier,
            redirect_uri=oauth_cb,
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    save_credentials(
        {
            "api_base_url": base,
            "access_token": body["access_token"],
            "refresh_token": body["refresh_token"],
        }
    )
    console.print(f"[green]Saved credentials for {base}[/green]")


@app.command()
def logout() -> None:
    """Revoke the stored refresh token and delete local credentials."""
    creds = load_credentials()
    if not creds:
        console.print("[yellow]Already logged out (no credentials file).[/yellow]")
        return
    api = api_base_url_from_store_or_default(creds)
    refresh = str(creds.get("refresh_token", ""))
    if refresh:
        try:
            logout_backend(api_base_url=api, refresh_token=refresh)
        except RuntimeError as e:
            console.print(f"[yellow]Server logout: {e} (clearing local file anyway)[/yellow]")
    clear_credentials_file()
    console.print("[green]Logged out.[/green]")


@app.command()
def whoami() -> None:
    """Show user id and role from the current access token (decoded locally)."""
    creds = load_credentials()
    if not creds:
        console.print("[red]Not logged in.[/red]")
        raise typer.Exit(1)
    token = str(creds.get("access_token", ""))
    try:
        payload = _decode_jwt_payload_unverified(token)
    except (ValueError, json.JSONDecodeError) as e:
        console.print(f"[red]Cannot read access token: {e}[/red]")
        raise typer.Exit(1) from e
    sub = payload.get("sub")
    role = payload.get("role")
    exp = payload.get("exp")
    typer.echo(f"api_base_url: {api_base_url_from_store_or_default(creds)}")
    typer.echo(f"user_id:      {sub}")
    typer.echo(f"role:         {role}")
    if isinstance(exp, int):
        typer.echo(f"access_exp:   {_exp_utc_str(exp)}")


@app.command()
def classify(
    name: Annotated[str, typer.Argument(help="Name to classify")],
) -> None:
    """Call GET /api/classify (Genderize-backed)."""
    try:
        client = _get_client()
        data = client.get_json("/api/classify", params={"name": name})
        _print_json(data)
    except InsightaApiError as e:
        _handle_api_err(e)


def _list_params_dict(
    *,
    page: int,
    limit: int,
    gender: Optional[str],
    age_group: Optional[str],
    country_id: Optional[str],
    min_age: Optional[int],
    max_age: Optional[int],
    min_gender_probability: Optional[float],
    min_country_probability: Optional[float],
    sort_by: str,
    order: str,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "page": page,
        "limit": limit,
        "sort_by": sort_by,
        "order": order,
    }
    if gender is not None:
        p["gender"] = gender
    if age_group is not None:
        p["age_group"] = age_group
    if country_id is not None:
        p["country_id"] = country_id
    if min_age is not None:
        p["min_age"] = min_age
    if max_age is not None:
        p["max_age"] = max_age
    if min_gender_probability is not None:
        p["min_gender_probability"] = min_gender_probability
    if min_country_probability is not None:
        p["min_country_probability"] = min_country_probability
    return p


@profiles_app.command("list")
def profiles_list(
    page: Annotated[int, typer.Option(min=1)] = 1,
    limit: Annotated[int, typer.Option(min=1, max=50)] = 10,
    gender: Annotated[Optional[str], typer.Option()] = None,
    age_group: Annotated[Optional[str], typer.Option()] = None,
    country_id: Annotated[Optional[str], typer.Option()] = None,
    min_age: Annotated[Optional[int], typer.Option()] = None,
    max_age: Annotated[Optional[int], typer.Option()] = None,
    min_gender_probability: Annotated[Optional[float], typer.Option()] = None,
    min_country_probability: Annotated[Optional[float], typer.Option()] = None,
    sort_by: Annotated[str, typer.Option()] = "created_at",
    order: Annotated[str, typer.Option()] = "desc",
) -> None:
    """Paginated profile list (same filters as the API)."""
    if sort_by not in ("age", "created_at", "gender_probability"):
        console.print("[red]sort_by must be age, created_at, or gender_probability[/red]")
        raise typer.Exit(1)
    if order not in ("asc", "desc"):
        console.print("[red]order must be asc or desc[/red]")
        raise typer.Exit(1)
    params = _list_params_dict(
        page=page,
        limit=limit,
        gender=gender,
        age_group=age_group,
        country_id=country_id,
        min_age=min_age,
        max_age=max_age,
        min_gender_probability=min_gender_probability,
        min_country_probability=min_country_probability,
        sort_by=sort_by,
        order=order,
    )
    try:
        client = _get_client()
        data = client.get_json("/api/profiles", params=params)
        _print_json(data)
    except InsightaApiError as e:
        _handle_api_err(e)


@profiles_app.command("search")
def profiles_search(
    query: Annotated[str, typer.Argument(help="Natural-language filter, e.g. 'male from NG'")],
    page: Annotated[int, typer.Option(min=1)] = 1,
    limit: Annotated[int, typer.Option(min=1, max=50)] = 10,
) -> None:
    """NL search over profiles."""
    try:
        client = _get_client()
        data = client.get_json(
            "/api/profiles/search",
            params={"q": query, "page": page, "limit": limit},
        )
        _print_json(data)
    except InsightaApiError as e:
        _handle_api_err(e)


@profiles_app.command("show")
def profiles_show(
    profile_id: Annotated[str, typer.Argument(help="Profile UUID")],
) -> None:
    """Fetch one profile by id."""
    try:
        client = _get_client()
        data = client.get_json(f"/api/profiles/{profile_id}")
        _print_json(data)
    except InsightaApiError as e:
        _handle_api_err(e)


@profiles_app.command("create")
def profiles_create(
    name: Annotated[str, typer.Option("--name", "-n", help="Full name to ingest")],
) -> None:
    """Create a profile (requires admin role on the API)."""
    try:
        client = _get_client()
        r = client.request("POST", "/api/profiles", json_body={"name": name})
        _print_json(r.json())
    except InsightaApiError as e:
        _handle_api_err(e)


@profiles_app.command("delete")
def profiles_delete(
    profile_id: Annotated[str, typer.Argument(help="Profile UUID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a profile (requires admin)."""
    if not yes:
        confirm = typer.confirm(f"Delete profile {profile_id}?")
        if not confirm:
            raise typer.Exit(0)
    try:
        client = _get_client()
        r = client.request("DELETE", f"/api/profiles/{profile_id}", expect_json=False)
        if r.status_code == 204:
            console.print("[green]Deleted.[/green]")
        else:
            _print_json(r.json()) if r.content else typer.echo(r.status_code)
    except InsightaApiError as e:
        _handle_api_err(e)


@profiles_app.command("export")
def profiles_export(
    output: Annotated[Path, typer.Option("--output", "-o", help="CSV file path")],
    gender: Annotated[Optional[str], typer.Option()] = None,
    age_group: Annotated[Optional[str], typer.Option()] = None,
    country_id: Annotated[Optional[str], typer.Option()] = None,
    min_age: Annotated[Optional[int], typer.Option()] = None,
    max_age: Annotated[Optional[int], typer.Option()] = None,
    min_gender_probability: Annotated[Optional[float], typer.Option()] = None,
    min_country_probability: Annotated[Optional[float], typer.Option()] = None,
    sort_by: Annotated[str, typer.Option()] = "created_at",
    order: Annotated[str, typer.Option()] = "desc",
) -> None:
    """Download CSV export (same filters as list; no pagination)."""
    if sort_by not in ("age", "created_at", "gender_probability"):
        console.print("[red]sort_by must be age, created_at, or gender_probability[/red]")
        raise typer.Exit(1)
    if order not in ("asc", "desc"):
        console.print("[red]order must be asc or desc[/red]")
        raise typer.Exit(1)
    base_params = _list_params_dict(
        page=1,
        limit=10,
        gender=gender,
        age_group=age_group,
        country_id=country_id,
        min_age=min_age,
        max_age=max_age,
        min_gender_probability=min_gender_probability,
        min_country_probability=min_country_probability,
        sort_by=sort_by,
        order=order,
    )
    params = {k: v for k, v in base_params.items() if k not in ("page", "limit")}
    params["format"] = "csv"
    try:
        client = _get_client()
        r = client.request("GET", "/api/profiles/export", params=params, expect_json=False)
        output.write_text(r.text, encoding="utf-8")
        console.print(f"[green]Wrote {output}[/green]")
    except InsightaApiError as e:
        _handle_api_err(e)

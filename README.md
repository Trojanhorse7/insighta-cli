# Insighta CLI

Python CLI for the **Insighta Labs+** profiles API. Commands send `X-API-Version: 1` and `Authorization: Bearer`, refresh access tokens on **401**, and store secrets in **`~/.insighta/credentials.json`** (0600).

**Repository:** [github.com/Trojanhorse7/insighta-cli](https://github.com/Trojanhorse7/insighta-cli) · **Web portal:** [github.com/Trojanhorse7/insighta-frontend](https://github.com/Trojanhorse7/insighta-frontend)

Install from Git:

```bash
python -m pip install "git+https://github.com/Trojanhorse7/insighta-cli.git"
```

## Install

From this directory (use a virtualenv if you prefer):

```bash
python -m pip install -e .
```

Run via **`insighta`** (if your Python `Scripts` directory is on `PATH`) or:

```bash
python -m insighta_cli --help
```

## Environment

| Variable | Purpose |
|----------|---------|
| `INSIGHTA_API_URL` | API base URL (default `http://127.0.0.1:8000`). Saved in credentials after `login`. |
| `INSIGHTA_GITHUB_CLIENT_ID` | GitHub OAuth App **client id** — must match **`GITHUB_CLIENT_ID`** on the API server. |
| `INSIGHTA_CLI_OAUTH_REDIRECT` | Local URL the **API** redirects to after GitHub (default `http://127.0.0.1:8765/callback`). Must match **`INSIGHTA_CLI_OAUTH_REDIRECT`** on the server and **`--redirect-uri`** if you override it. |

**GitHub OAuth App** (classic “OAuth App”): you can register **only one** authorization callback URL. Set it to **`{INSIGHTA_API_URL}/auth/github/callback`** (same host as `BACKEND_PUBLIC_URL` on the API). The CLI does **not** register the loopback on GitHub; the API forwards the `code` to your machine.

Backend parity: match your Insighta API `.env` (especially `INSIGHTA_CLI_OAUTH_REDIRECT`, `BACKEND_PUBLIC_URL`). See the backend `.env.example`.

## Auth

1. On GitHub: **Authorization callback URL** = **`https://<your-api-host>/auth/github/callback`** (exactly; includes local dev if that is your API).
2. `insighta login` sends `redirect_uri` = that same URL to GitHub, listens on **`INSIGHTA_CLI_OAUTH_REDIRECT`**, receives a redirect from the API with `?code=` or `?error=`, then calls **`POST /auth/github/cli`**.

Use `insighta login --no-browser` if you must copy the authorize URL manually. Use `--api-url` / `--github-client-id` / `--redirect-uri` to override env defaults.

`insighta logout` calls **`POST /auth/logout`** with the stored refresh token and deletes the credentials file.

## Commands

- `insighta whoami` — show JWT `sub` / `role` / access expiry (decoded locally, not verified).
- `insighta classify NAME` — `GET /api/classify?name=...`
- `insighta profiles list` — paginated list; options mirror list query params (gender, `age-group`, `country-id`, ages, probabilities, `sort-by`, `order`, `page`, `limit` ≤ 50).
- `insighta profiles search "natural language query"` — `GET /api/profiles/search`
- `insighta profiles show PROFILE_ID`
- `insighta profiles create --name "..."` — admin only on the API.
- `insighta profiles delete PROFILE_ID`
- `insighta profiles export -o out.csv` — same filters as list; `format=csv` is set for you.

## Repository layout

```
insighta-cli/
  pyproject.toml
  README.md
  insighta_cli/
    __init__.py
    __main__.py
    main.py       # Typer commands
    config.py     # paths + secrets file
    auth.py       # PKCE + OAuth callback server + refresh/logout HTTP
    client.py     # httpx + version header + token rotation
```

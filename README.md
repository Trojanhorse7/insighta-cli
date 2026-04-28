# Insighta CLI

Python CLI for the **Insighta Labs+** profiles API (`../STAGE_ONE`). Commands send `X-API-Version: 1` and `Authorization: Bearer`, refresh access tokens on **401**, and store secrets in **`~/.insighta/credentials.json`** (0600).

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
| `INSIGHTA_CLI_OAUTH_REDIRECT` | Loopback callback URL (default `http://127.0.0.1:8765/callback`). **Register this** in the GitHub OAuth App’s authorized redirect URLs. |

Backend parity: see `../STAGE_ONE/.env.example` (`INSIGHTA_CLI_OAUTH_REDIRECT`, GitHub OAuth, JWT lifetimes).

## Auth

1. Register redirect `http://127.0.0.1:8765/callback` on your GitHub OAuth App (same app as the backend).
2. `insighta login` opens a browser, receives the OAuth `code` on localhost, exchanges via **`POST /auth/github/cli`**, then saves tokens.

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

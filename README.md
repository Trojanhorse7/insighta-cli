# Insighta CLI

Python **Typer** CLI for the **Insighta Labs+** profiles API. Every request sends **`X-API-Version: 1`** and **`Authorization: Bearer <access>`**. On **401**, the client tries **`POST /auth/refresh`** with the stored refresh token and retries once (then surfaces an error — run `insighta login` again if refresh is invalid).

**Credentials** are stored in **`~/.insighta/credentials.json`** with restrictive permissions where the OS allows (intended **0600**). The file holds `api_base_url`, `access_token`, and `refresh_token`.

**Repositories:** [insighta-cli](https://github.com/Trojanhorse7/insighta-cli) · [Web portal](https://github.com/Trojanhorse7/insighta-frontend). Point **`INSIGHTA_API_URL`** at your deployed Django API (same host as **`BACKEND_PUBLIC_URL`** on the server).

---

## Install

**From Git (global `insighta` command once `Scripts` / `bin` is on `PATH`):**

```bash
python -m pip install "git+https://github.com/Trojanhorse7/insighta-cli.git"
```

**Editable (from this repo):**

```bash
python -m pip install -e .
```

**Run without PATH:**

```bash
python -m insighta_cli --help
```

Entry point: **`insighta`** (`pyproject.toml` → `[project.scripts]`).

---

## Environment

| Variable | Purpose |
|----------|---------|
| `INSIGHTA_API_URL` | API base URL (default `http://127.0.0.1:8000`). Overridable with `login --api-url`; stored in credentials after login. |
| `INSIGHTA_GITHUB_CLIENT_ID` | GitHub OAuth App **client id** — must match **`GITHUB_CLIENT_ID`** on the API. Overridable with `login --github-client-id`. |
| `INSIGHTA_CLI_OAUTH_REDIRECT` | Local URL the **API** redirects to after GitHub hits the API callback (default `http://127.0.0.1:8765/callback`). Must match the API’s **`INSIGHTA_CLI_OAUTH_REDIRECT`** and `login --redirect-uri` if you override it. |

**GitHub OAuth App:** register **one** authorization callback URL: **`{API_ORIGIN}/auth/github/callback`** (same as `BACKEND_PUBLIC_URL` on the server). The CLI does **not** register loopback on GitHub; the API forwards `code` / `error` to your machine.

See the backend **`.env.example`** for server-side parity (`BACKEND_PUBLIC_URL`, `INSIGHTA_CLI_OAUTH_REDIRECT`, GitHub secrets).

---

## Auth flow

1. **`insighta login`** builds a GitHub authorize URL with PKCE; **`redirect_uri`** is always **`{api}/auth/github/callback`**.
2. GitHub redirects to the API; for CLI sessions the API **302**s to **`INSIGHTA_CLI_OAUTH_REDIRECT`** with query params; the CLI’s local listener reads them.
3. CLI **`POST /auth/github/cli`** with `code`, `code_verifier`, and `redirect_uri` = the same GitHub callback URL.
4. Tokens are saved; CLI calls **`GET /auth/me`** and prints **`Logged in as @username`** when possible.

Options: **`--no-browser`** (print URL), **`--api-url`**, **`--github-client-id`**, **`--redirect-uri`**.

**`insighta logout`** — **`POST /auth/logout`** with the stored refresh token, then deletes the credentials file.

**`insighta whoami`** — decodes the access JWT **locally** (not verified) and prints `user_id` (`sub`), `role`, and access expiry.

---

## Commands reference

### Account

| Command | Description |
|---------|-------------|
| `insighta login` | GitHub OAuth; saves `~/.insighta/credentials.json`. |
| `insighta logout` | Revokes refresh on server; clears local credentials. |
| `insighta whoami` | JWT claims + API URL from file. |

### Profiles — list & search

**`insighta profiles list`** — paginated **`GET /api/profiles`**. Options (mirror the API):

| Option | Maps to API |
|--------|-------------|
| `--page`, `--limit` | Pagination (`limit` ≤ 50) |
| `--gender` | `gender` |
| `--age-group` | `age_group` |
| `--country` | `country_id` (e.g. `NG`) |
| `--min-age`, `--max-age` | `min_age`, `max_age` |
| `--min-gender-probability`, `--min-country-probability` | probability filters |
| `--sort-by` | `age` \| `created_at` \| `gender_probability` |
| `--order` | `asc` \| `desc` |

**`insighta profiles search "…"`** — **`GET /api/profiles/search`** with `q`. Supports `--page`, `--limit`.

Examples:

```bash
insighta profiles list --gender male
insighta profiles list --country NG --age-group adult
insighta profiles list --min-age 25 --max-age 40
insighta profiles list --sort-by age --order desc --page 2 --limit 20
insighta profiles search "young males from nigeria"
```

### Profiles — detail, create, export, extras

| Command | Description |
|---------|-------------|
| `insighta profiles show <uuid>` | One profile (detail table). |
| `insighta profiles get <uuid>` | Same as **`show`**. |
| `insighta profiles create --name "Harriet Tubman"` | **`POST /api/profiles`** (API must grant **admin**). |
| `insighta profiles delete <uuid>` | **`DELETE`** (admin); confirms unless **`--yes`**. |
| `insighta profiles export --format csv` | **`GET /api/profiles/export`** with list filters; CSV only today. |

**Export output**

- **`--format csv`** (default **`csv`**; other values are rejected).
- **`--output` / `-o`** optional. If omitted, writes **`insighta-profiles-export-<UTC-timestamp>.csv`** in the **current working directory**.
- Same filters as **`profiles list`** (`--gender`, `--country`, ages, probabilities, **`--sort-by`**, **`--order`**).

Example:

```bash
insighta profiles export --format csv --gender male --country NG
insighta profiles export -o ./profiles.csv
```

### Classify

**`insighta classify "Jane"`** — **`GET /api/classify?name=...`** (Genderize-backed).

---

## Output & UX

- **List / search:** [Rich](https://github.com/Textualize/rich) **table** (id, name, gender, age, age_group, country_id, gender_probability) plus a summary line (page, row count, total, total_pages).
- **Profile detail:** two-column field/value table.
- **Create / classify / errors:** JSON or message text as appropriate.
- **Progress:** status spinners during network calls (e.g. “Loading profiles…”).
- **Errors:** API failures print in **red** on **stderr**; **401** hints to run **`insighta login`** again.

---

## Repository layout

```
insighta-cli/
  pyproject.toml
  README.md
  insighta_cli/
    __init__.py
    __main__.py
    main.py       # Typer commands + table output
    config.py     # paths + credentials load/save
    auth.py       # PKCE + local callback server + refresh/logout HTTP
    client.py     # httpx + version header + token rotation on 401
```

---

## Related

- **Portal:** [github.com/Trojanhorse7/insighta-frontend](https://github.com/Trojanhorse7/insighta-frontend)
- **Backend:** Django **Insighta Labs+** API README (endpoints, rate limits, RBAC, `.env.example`).

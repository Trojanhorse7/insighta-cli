# Insighta CLI

Python **Typer** CLI for the **Insighta Labs+** profiles API. Every request sends **`X-API-Version: 1`** and **`Authorization: Bearer <access>`**. On **401**, the client tries **`POST /auth/refresh`** with the stored refresh token and retries once (then surfaces an error — run `insighta login` again if refresh is invalid).

**Credentials** are stored in **`~/.insighta/credentials.json`** with restrictive permissions where the OS allows (intended **0600**). The file holds:

- **`api_base_url`** — API you authenticated against (re-used on the next `insighta login` if you omit `--api-url`).
- **`github_client_id`** — GitHub **CLI** OAuth App client id (must match **`GITHUB_CLI_CLIENT_ID`** on the API); saved on successful login.
- **`access_token`** / **`refresh_token`** — session tokens.

Resolution order for **client id** on login: **`--github-client-id`** → **`INSIGHTA_GITHUB_CLIENT_ID`** → value from **`credentials.json`**. For **API URL**: **`--api-url`** → stored **`api_base_url`** → **`INSIGHTA_API_URL`** → default `http://127.0.0.1:8000`.

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
| `INSIGHTA_GITHUB_CLIENT_ID` | GitHub **CLI** OAuth App client id — must match **`GITHUB_CLI_CLIENT_ID`** on the API. Overridable with `login --github-client-id`. |
| `INSIGHTA_CLI_OAUTH_REDIRECT` | Local listener URL (default `http://127.0.0.1:8765/callback`). Register **this exact URL** as the CLI OAuth App’s callback on GitHub; must match the API **`INSIGHTA_CLI_OAUTH_REDIRECT`** and `login --redirect-uri` if overridden. |

**GitHub:** create one OAuth App for the **portal** (callback **`{BACKEND_PUBLIC_URL}/auth/github/callback`**) and one for the **CLI** with callback = your loopback URL. See backend **`.env.example`** (sets **`GITHUB_CLI_*`** and **`INSIGHTA_CLI_OAUTH_REDIRECT`**).

---

## Auth flow

1. **`insighta login`** opens GitHub with PKCE; **`redirect_uri`** is **`INSIGHTA_CLI_OAUTH_REDIRECT`** (local listener — must match the **CLI** OAuth App’s registered callback on GitHub).
2. GitHub redirects the browser to that loopback URL with `?code=` / `?error=`; the CLI captures it.
3. CLI **`POST /auth/github/cli`** on the API with `code`, `code_verifier`, and the same **`redirect_uri`**; the API validates it against **`INSIGHTA_CLI_OAUTH_REDIRECT`** and exchanges with **`GITHUB_CLI_CLIENT_ID`** / **`GITHUB_CLI_CLIENT_SECRET`**.
4. Tokens are saved; CLI may call **`GET /auth/me`** and print **`Logged in as @username`**.

Options: **`--no-browser`** (print URL), **`--api-url`**, **`--github-client-id`**, **`--redirect-uri`** (must still match the configured **`INSIGHTA_CLI_OAUTH_REDIRECT`** allowlist on the API).

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

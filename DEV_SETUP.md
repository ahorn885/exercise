# Dev setup

How to get the app and the Layer 0 ETL running on a fresh machine.

## Common (any OS)

1. Clone, install deps:
   ```
   pip install -r requirements.txt
   ```
2. Copy the env template and fill it in:
   ```
   cp .env.example .env
   # generate SECRET_KEY:
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   # then paste into .env
   ```
3. Set `DATABASE_URL` in `.env` to a Postgres / Neon connection string.
   The app is Postgres-only (SQLite path retired 2026-05-16, PR13);
   `get_db()` raises if `DATABASE_URL` is unset. Use a Neon dev branch
   for local work — the production branch should not be the target of
   routine local runs.
4. Run:
   ```
   flask --app app run
   ```

## Redesign migration — CSP report-only mode

While porting screens to the redesign shell, set `CSP_REPORT_ONLY=1` in
`.env` so Content-Security-Policy violations are **logged, not enforced**
(the header flips to `Content-Security-Policy-Report-Only`). This lets you
iterate without the browser blocking not-yet-cleaned inline styles/handlers.

```
CSP_REPORT_ONLY=1
```

**Flip it back off (unset, enforced) before marking any screen done** — zero
console violations under the enforced header is part of the per-screen
Definition of Done (`docs/redesign/CONVENTIONS.md` §G). The flag is read in
`app.py` and already documented in `.env.example`.

## Vercel link (optional, for prod env-var pull)

```
vercel link --project exercise --scope andy-horns-projects --yes
vercel env pull .env --environment=preview --yes   # or =production
```

`.vercel/` is gitignored.

## Layer 0 reference data

Postgres-only. The `layer0.*` tables are the source of truth (epic #488).
Author edits as reviewed SQL migrations under `etl/migrations/layer0/`,
validated by the `validate_layer0` gate — the legacy "edit a spreadsheet
and re-run the ETL" path is retired (frozen under
`etl/_frozen_xlsx_authoring/`).

Validate locally against a dev branch (the production Neon branch should
not be the target of routine work):

```
python -m etl.layer0.validate_layer0
```

See `etl/migrations/layer0/README.md` for the authoring flow + the
invalidation-not-overwrite versioning model, and `etl/README.md` for the
overall layout and the gate.

## Windows gotchas

Discovered during the 2026-05-08 Windows bring-up. Capturing here so
the next person doesn't rediscover them.

### 1. PowerShell execution policy blocks npm / vercel shims

One-time fix:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. `python` vs `py`

Windows ships a Microsoft Store stub at `python.exe` that intercepts the
bare command and pops up the Store. Use the `py` launcher instead:

```powershell
py -m pip install -r requirements.txt
py -m etl.layer0.validate_layer0
```

### 3. UTF-8 default encoding

`Path.read_text()` / `open()` without `encoding=` default to `cp1252` on
Windows and choke on the UTF-8 sources (em-dashes, arrows, accented
characters). All ETL call sites now declare `encoding="utf-8"` explicitly,
but as a belt-and-braces measure you can set:

```powershell
$env:PYTHONUTF8 = "1"
```

### 4. `vercel env pull` is interactive

It prompts to overwrite an existing `.env`. Pass `--yes` for non-TTY use:

```powershell
vercel env pull .env --environment=preview --yes
```

### 5. Loading `.env` in PowerShell 5.1

Bash `set -a; . ./.env; set +a` doesn't work. Use:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)\s*$') {
    [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'), 'Process')
  }
}
```

### Full Windows bring-up sequence

```powershell
# In repo root
vercel link --project exercise --scope andy-horns-projects --yes
vercel env pull .env --environment=preview --yes
# Manually edit .env to point DATABASE_URL at a Neon dev branch you created
py -m pip install -r requirements.txt

# Per-run: load env then run
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)\s*$') {
    [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'), 'Process')
  }
}
$env:PYTHONUTF8 = "1"
py -m etl.layer0.validate_layer0
```

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

## Vercel link (optional, for prod env-var pull)

```
vercel link --project exercise --scope andy-horns-projects --yes
vercel env pull .env --environment=preview --yes   # or =production
```

`.vercel/` is gitignored.

## Layer 0 ETL

Postgres-only. Set `DATABASE_URL` to a dev branch (the production Neon
branch should not be the target of routine ETL runs):

```
python -m etl.layer0.run --version-tag 1.3.1
```

Reports land in `etl/reports/`. The run is idempotent within a version
tag (delete-and-reinsert) and superseding (sets `superseded_at` on the
prior version) when the tag changes.

See `etl/README.md` for the full versioning model and rollback path.

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
py -m etl.layer0.run --version-tag 1.3.1
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
py -m etl.layer0.run --version-tag 1.3.1
```

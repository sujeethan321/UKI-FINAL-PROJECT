$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
& '.\backend\.venv\Scripts\python.exe' -B backend/scripts/viva_pending_migrations.py --plan --database lankapex_viva_db
if($LASTEXITCODE -ne 0){throw 'STOP: source preparation failed; no retry'}
& '.\backend\.venv\Scripts\python.exe' -B backend/scripts/viva_pending_migrations.py --plan --database lankapex_migration_verify_viva20261124
if($LASTEXITCODE -ne 0){throw 'STOP: rehearsal preparation failed; no retry'}
Write-Output 'PREPARED_NOT_EXECUTED; DATABASE_ACTIONS=0; EXECUTION_RELEASE_REQUIRED=yes'

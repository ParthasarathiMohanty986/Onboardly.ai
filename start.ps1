$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
python manage.py runserver 127.0.0.1:8000 --noreload

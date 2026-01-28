pg_backup.ps1 — Backup & automation guide

Overview
--------
Small PowerShell utility to create PostgreSQL backups on Windows (works without Docker).

Quick usage
-----------
- Interactive (prompts for DB password):
  .\pg_backup.ps1 -Host localhost -DbName trademeup -User trademeup_user -Format custom -Compress

- Automated (use environment variable PGPASSWORD):
  $env:PGPASSWORD = 'your_secret'; .\pg_backup.ps1 -Host localhost -DbName trademeup -User trademeup_user -Format custom -OutDir C:\backups -Compress; Remove-Item Env:PGPASSWORD

Parameters
----------
- Host, Port, DbName, User — connection details
- Format: `custom` (pg_dump custom, recommended) or `plain` (SQL file)
- OutDir: directory for backups (default: ./backups)
- Compress: produce a `.zip` and delete raw dump
- RetentionDays: delete backups older than X days (default 30)
- UseEnvPassword: when set, uses $env:PGPASSWORD (do not prompt)

Scheduling
----------
Use Windows Task Scheduler to run the script daily/weekly. Example Task action:
- Program/script: powershell
- Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\TradeMeUp\scripts\pg_backup.ps1" -Host localhost -DbName trademeup -User trademeup_user -Format custom -Compress
- Configure a trigger (daily 02:00)

Security notes
--------------
- Do not hardcode passwords in scripts committed to source control.
- For automation, prefer storing credentials in Windows Credential Manager and inject into the script securely.
- Keep at least 2-3 backup copies (daily/weekly/monthly) and test restores.

Restore examples
----------------
- Restore custom dump (creates DB):
  pg_restore -U trademeup_user -h <host> -p <port> -d postgres -C -v C:\backups\trademeup_backup_20260128_020304.dump

- Restore plain SQL:
  psql -U trademeup_user -h <host> -p <port> -d trademeup -f C:\backups\trademeup_backup_20260128_020304.sql

Support
-------
If you want, I can:
1) Add a Windows Task Scheduler registration script, or
2) Add an example using Windows Credential Manager to fetch password securely.

Tell me which option you prefer and I will add it. (Short answer: "sched" or "cred")
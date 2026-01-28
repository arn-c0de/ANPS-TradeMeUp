<#
Simple PostgreSQL backup script for Windows (PowerShell)

Usage examples:
  # Prompt for password interactively, custom format, compressed, keep 30 days
  .\pg_backup.ps1 -Host localhost -Port 5432 -DbName trademeup -User trademeup_user -Format custom -Compress -RetentionDays 30

  # Use PGPASSWORD environment variable (suitable for automation)
  $env:PGPASSWORD = 'secret'; .\pg_backup.ps1 -Host localhost -DbName trademeup -User trademeup_user -Format custom -OutDir C:\backups -Compress
  Remove-Item Env:PGPASSWORD

Notes:
- Requires `pg_dump.exe` to be installed (Postgres bin folder). If not in PATH, set PG_BIN environment variable or change $DefaultPgBin.
- This script DOES NOT store plain passwords in source. Use environment variable PGPASSWORD or Windows Credential Manager in production.
#>
param(
    [string]$Host = "localhost",
    [int]$Port = 5432,
    [string]$DbName = "trademeup",
    [string]$User = "postgres",
    [ValidateSet('custom','plain')]
    [string]$Format = "custom",
    [string]$OutDir = "$(Join-Path -Path (Get-Location) -ChildPath 'backups')",
    [switch]$Compress,
    [int]$RetentionDays = 30,
    [switch]$UseEnvPassword # If specified, use $env:PGPASSWORD rather than prompting
)

# Determine pg_dump path
$DefaultPgBin = "C:\Program Files\PostgreSQL\14\bin"
if ($env:PG_BIN) { $PgBin = $env:PG_BIN } elseif (Test-Path -Path "$DefaultPgBin\pg_dump.exe") { $PgBin = $DefaultPgBin } else { $PgBin = $env:PATH.Split(';') | Where-Object { Test-Path (Join-Path $_ 'pg_dump.exe') } | Select-Object -First 1 }
if (-not $PgBin) { Write-Error "pg_dump.exe not found. Set PG_BIN or install PostgreSQL client tools."; exit 1 }
$PgDump = if ($PgBin -match 'pg_dump.exe$') { $PgBin } else { Join-Path $PgBin 'pg_dump.exe' }

# Ensure output directory exists
if (-not (Test-Path -Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# Get password securely
if ($UseEnvPassword -and $env:PGPASSWORD) {
    $PlainPassword = $env:PGPASSWORD
} else {
    $SecurePwd = Read-Host -Prompt "Postgres password for $User@$Host" -AsSecureString
    $PlainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePwd))
}

# Timestamped filename
$TimeStamp = Get-Date -Format yyyyMMdd_HHmmss
$BaseName = "${DbName}_backup_${TimeStamp}"
if ($Format -eq 'custom') { $DumpFile = Join-Path $OutDir "${BaseName}.dump" } else { $DumpFile = Join-Path $OutDir "${BaseName}.sql" }

# Build pg_dump arguments
$Args = @("-h", $Host, "-p", $Port.ToString(), "-U", $User)
if ($Format -eq 'custom') { $Args += @("-F", "c", "-b", "-v") }
$Args += @("-f", $DumpFile, $DbName)

# Run pg_dump (use env var PGPASSWORD for non-interactive)
$oldEnv = $env:PGPASSWORD
$env:PGPASSWORD = $PlainPassword
try {
    Write-Host "Starting pg_dump -> $DumpFile"
    $proc = Start-Process -FilePath $PgDump -ArgumentList $Args -NoNewWindow -Wait -PassThru -RedirectStandardError ([IO.Path]::Combine($OutDir, "${BaseName}_pg_dump.err"))
    if ($proc.ExitCode -ne 0) {
        Write-Error "pg_dump failed with exit code $($proc.ExitCode). Check ${BaseName}_pg_dump.err"
        exit $proc.ExitCode
    }
    Write-Host "pg_dump completed successfully"
} finally {
    # Clean up sensitive env var unless the caller explicitly set it outside
    if (-not $UseEnvPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
    else { $env:PGPASSWORD = $oldEnv }
}

# Optionally compress the dump
if ($Compress) {
    $ZipFile = Join-Path $OutDir "${BaseName}.zip"
    Write-Host "Compressing $DumpFile -> $ZipFile"
    Compress-Archive -Path $DumpFile -DestinationPath $ZipFile -Force
    if ($?) { Remove-Item $DumpFile -Force }
}

# Cleanup old backups
if ($RetentionDays -gt 0) {
    Write-Host "Removing backups older than $RetentionDays days in $OutDir"
    Get-ChildItem -Path $OutDir -File | Where-Object { ($_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays)) } | ForEach-Object { Write-Host "Removing: $($_.FullName)"; Remove-Item $_.FullName -Force }
}

Write-Host "Backup completed: " -NoNewline; if ($Compress) { Write-Host $ZipFile } else { Write-Host $DumpFile }

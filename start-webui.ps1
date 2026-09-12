# start-webui.ps1 - 启动 PEQ WebUI（EqualizerAPO 版后端 :9100）
# APO 配置已迁移到项目内可写目录，不再需要管理员权限/UAC。
$ErrorActionPreference = 'Stop'
$Port = 9100

$existing = netstat -ano | Select-String (":$Port\s") | Select-String 'LISTENING'
if ($existing) {
    Write-Host "PEQ WebUI already running on http://127.0.0.1:$Port"
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutLog = Join-Path $ScriptDir 'peq-webui.log'
$ErrLog = Join-Path $ScriptDir 'peq-webui.err.log'

$p = Start-Process -FilePath 'py' `
    -ArgumentList 'mixer_web.py', '--port', "$Port" `
    -WorkingDirectory $ScriptDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

Start-Sleep -Milliseconds 800
if ($p.HasExited) {
    if ($p.ExitCode -eq 0) {
        Write-Host "PEQ WebUI already running on http://127.0.0.1:$Port (singleton lock held)"
        exit 0
    }
    Write-Host "PEQ WebUI failed to start, exit code $($p.ExitCode)"
    if (Test-Path $ErrLog) { Get-Content $ErrLog }
    exit 1
}

Write-Host "PEQ WebUI started on http://127.0.0.1:$Port (pid $($p.Id))"

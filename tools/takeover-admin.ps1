# takeover-admin.ps1
# 一次性把 EqualizerAPO ConfigPath 迁移到本项目 apo-config（需管理员 PowerShell）。
# 为什么需要本脚本：install() 在 Program Files\EqualizerAPO\config 已存在时不会自动
# migrate，只会去授权 Program Files（见部署手册 / 坑位 B1）。
# 用法（管理员）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\takeover-admin.ps1
# 幂等：已托管则仅确保 hl-active.txt 存在。

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONDONTWRITEBYTECODE = '1'

Write-Host "== PEQ-WebUI APO takeover =="
Write-Host "Project: $Root"

# 优先用系统 py；失败则 python
$py = $null
foreach ($cand in @('py', 'python')) {
  try {
    & $cand --version | Out-Null
    if ($LASTEXITCODE -eq 0) { $py = $cand; break }
  } catch {}
}
if (-not $py) {
  Write-Error "Python not found (py/python)."
  exit 1
}

$code = @'
import json, os, sys
sys.path.insert(0, os.getcwd())
from apo_backend import ApoBackend

a = ApoBackend()
# 显式迁移（install() 在 Program Files 已存在时可能不会走迁移分支）
a.migrate_to_user_config_dir()
# 确保 auto-install 允许，并写入 Managed Include
try:
    a.set_auto_install_enabled(True)
except Exception:
    pass
st = a.install(by='takeover-admin')
print(json.dumps(st, ensure_ascii=False, indent=2))
'@

$tmpPy = Join-Path $env:TEMP ('peq_takeover_' + [guid]::NewGuid().ToString() + '.py')
# 仅在 TEMP 写一次性脚本；若沙箱拦截 TEMP，可把本 ps1 的逻辑改为 py -c 单行
Set-Content -Path $tmpPy -Value $code -Encoding UTF8
try {
  & $py $tmpPy
  $ok = $LASTEXITCODE
} finally {
  Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
}

if ($ok -ne 0) {
  Write-Host "takeover finished with exit code $ok" -ForegroundColor Yellow
} else {
  Write-Host "Done. Restart the WebUI service and check /api/status -> apo.managed=true" -ForegroundColor Green
}

Write-Host "If you move this project folder later, re-run this script (ConfigPath is absolute)."

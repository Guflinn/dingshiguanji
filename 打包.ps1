# 重新打包 定时关机.exe
#
# 用法：右键“使用 PowerShell 运行”，或在 PowerShell 中执行  .\打包.ps1
#
# 说明：DSH 工作区被标记为“低完整性”，新建的 exe 会继承该标记，
#       导致 exe 以低完整性进程运行、无法在 %TEMP% 解压自身
#       （表现为弹窗 “Could not create temporary directory!”）。
#       所以打包后必须把 exe 的完整性级别改为“中等”，本脚本已自动处理。

$ErrorActionPreference = "Stop"
$ws = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = if ($env:DSH_PYTHON) { $env:DSH_PYTHON } else { "python.exe" }

if (-not (Test-Path $py)) {
    Write-Host "找不到 Python：$py" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path "$ws\.tmp" | Out-Null
$env:TMP = "$ws\.tmp"
$env:TEMP = "$ws\.tmp"
$env:PYTHONPATH = "$ws\pylibs"

Set-Location $ws
Write-Host "开始打包..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --onefile --noconsole --name "定时关机" `
    --icon "$ws\icon.ico" --workpath "$ws\build" --distpath "$ws\dist" `
    --specpath "$ws" "$ws\ds_shutdown.py"

if (-not (Test-Path "$ws\dist\定时关机.exe")) {
    Write-Host "打包失败：未生成 exe" -ForegroundColor Red
    exit 1
}

Move-Item "$ws\dist\定时关机.exe" "$ws\定时关机.exe" -Force

# 关键一步：修正完整性级别，否则在工作区内无法解压运行
icacls "$ws\定时关机.exe" /setintegritylevel Medium | Out-Null

Remove-Item "$ws\dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$ws\.tmp" -Recurse -Force -ErrorAction SilentlyContinue

$size = "{0:N1} MB" -f ((Get-Item "$ws\定时关机.exe").Length / 1MB)
Write-Host "打包完成：$ws\定时关机.exe  ($size)" -ForegroundColor Green

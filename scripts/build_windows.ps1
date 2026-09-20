$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean daocha.spec

Write-Host ""
Write-Host "打包完成。可执行文件："
Write-Host "  dist\Daocha\Daocha.exe"
Write-Host "把整个 dist\Daocha 文件夹拷到另一台 Windows 电脑即可运行。"

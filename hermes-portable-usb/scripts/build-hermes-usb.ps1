<#
.SYNOPSIS
    构建 Hermes Agent 便携版 U盘
.DESCRIPTION
    自动下载 Python 3.11 embeddable、安装 Hermes Agent 和所有依赖，
    配置好启动脚本，复制到 U盘即可即插即用。
    同事只需要在 .env 里填 API Key。
.NOTES
    需要管理员权限？不需要，但需要能 pip install。
    需要网络：是（下载 Python、pip install Hermes）
    网络要求：能访问 python.org、pypi.org、github.com
#>

param(
    [string]$UsbPath = "",
    [switch]$Help
)

if ($Help) {
    Write-Host @"
用法: .\build-hermes-usb.ps1 [-UsbPath "D:\"]

参数:
  -UsbPath     U盘路径，例如 D:\ 或 E:\
               不传则构建到当前目录下的 hermes-usb 文件夹

说明:
  1. 插上 U盘，记下盘符
  2. 以 PowerShell 运行此脚本
  3. 等待构建完成（约 5-10 分钟，取决于网速）
  4. 把生成的文件复制到 U盘根目录
  5. 同事插上 U盘 → 双击 start-hermes.bat → 输入 API Key → 开用
"@
    exit
}

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

# ===== 目标路径 =====
if ($UsbPath) {
    $DestRoot = $UsbPath
    if (-not $DestRoot.EndsWith("\")) { $DestRoot += "\" }
    $DestRoot = Join-Path $DestRoot "HermesAgent"
} else {
    $DestRoot = Join-Path (Get-Location) "hermes-usb"
}

$PythonDir   = Join-Path $DestRoot "python"
$HermesHome  = Join-Path $DestRoot "hermes_home"
$ScriptsDir  = Join-Path $PythonDir "Scripts"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   Hermes Agent 便携版 U盘 构建工具" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "目标路径: $DestRoot" -ForegroundColor Yellow
Write-Host ""

# 创建目录
New-Item -ItemType Directory -Path $DestRoot -Force | Out-Null
New-Item -ItemType Directory -Path $PythonDir -Force | Out-Null
New-Item -ItemType Directory -Path $HermesHome -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $HermesHome "sessions") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $HermesHome "skills") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $HermesHome "logs") -Force | Out-Null

# ===== 1. 下载 Python 3.11 可移植版 =====
Write-Host "[1/5] 下载 Python 3.11 embeddable ..." -ForegroundColor Green
$PythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
$PythonZip = Join-Path $DestRoot "python-embed.zip"
try {
    Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip -UseBasicParsing
} catch {
    Write-Host "下载失败，尝试 Python 3.12 ..." -ForegroundColor Yellow
    $PythonUrl = "https://www.python.org/ftp/python/3.12.9/python-3.12.9-embed-amd64.zip"
    $PythonZip = Join-Path $DestRoot "python-embed.zip"
    Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip -UseBasicParsing
}

Write-Host "   解压中 ..."
Expand-Archive -Path $PythonZip -DestinationPath $PythonDir -Force
Remove-Item $PythonZip -Force

# ===== 2. 开启 site-packages 支持 =====
Write-Host "[2/5] 配置可移植 Python（开启 site-packages）..." -ForegroundColor Green
$PthFile = Get-ChildItem -Path $PythonDir -Filter "python*._pth" | Select-Object -First 1
if ($PthFile) {
    $content = Get-Content $PthFile.FullName
    # 确保 #import site 没有被注释
    $content = $content -replace "^#import site", "import site"
    Set-Content -Path $PthFile.FullName -Value $content
    Write-Host "   已修改 $($PthFile.Name) 启用 site-packages"
}

# ===== 3. 安装 pip 和 Hermes Agent =====
Write-Host "[3/5] 安装 pip ..." -ForegroundColor Green
$PythonExe = Join-Path $PythonDir "python.exe"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipFile = Join-Path $DestRoot "get-pip.py"

Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipFile -UseBasicParsing
& $PythonExe $GetPipFile --no-warn-script-location
Remove-Item $GetPipFile -Force

# 验证 pip
$PipExe = Join-Path $ScriptsDir "pip.exe"
if (-not (Test-Path $PipExe)) {
    $PipExe = Get-ChildItem -Path $PythonDir -Recurse -Filter "pip.exe" | Select-Object -First 1
    if (-not $PipExe) {
        Write-Host "错误: pip 安装失败！" -ForegroundColor Red
        exit 1
    }
    $PipExe = $PipExe.FullName
}

Write-Host "[4/5] 安装 Hermes Agent（这步需要网络，约3-5分钟）..." -ForegroundColor Green
$HermesPipLog = Join-Path $DestRoot "pip-install.log"

# 先升级 pip 本身
& $PipExe install --upgrade pip --quiet 2>&1 | Out-Host

# 安装 Hermes Agent（核心依赖，不装可选的 messaging 等）
Write-Host "   安装核心依赖 ..." -ForegroundColor Yellow
& $PipExe install "hermes-agent" --no-warn-script-location 2>&1 | Tee-Object -FilePath $HermesPipLog

Write-Host "[5/5] 创建配置文件和启动脚本 ..." -ForegroundColor Green

# ===== 4. 创建 .env 模板 =====
$EnvContent = @'
# =============================================================================
# Hermes Agent 便携版 - 环境配置
# =============================================================================
# 在这里填入你的 API Key！！！
# 
# 如果你用 OpenRouter（推荐，支持200+模型）:
#   1. 打开 https://openrouter.ai/keys
#   2. 注册账号 → 创建 API Key
#   3. 把 Key 填到下面
#
# 如果你用 DeepSeek（便宜，20元起）:
#   1. 打开 https://platform.deepseek.com/api_keys
#   2. 注册 → 创建 API Key
#   3. 在 config.yaml 里把 provider 改成 deepseek
#   4. 把 Key 填到下面
#
# 如果你用其他提供商:
#   第一次启动后运行: hermes model
#   按提示选择你的提供商

# 在这里填入你的 API Key（去掉 # 号）
# OPENROUTER_API_KEY=sk-or-...xxxx

# Gemini（免费，支持看图）
# GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxx

# DeepSeek
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
'@
[System.IO.File]::WriteAllText((Join-Path $HermesHome ".env"), $EnvContent)  # UTF-8 without BOM

# ===== 5. 创建 config.yaml =====
$ConfigContent = @"
model:
  default: openrouter/auto
  provider: openrouter
  base_url: ""

agent:
  max_turns: 90
  api_max_retries: 3
  tool_use_enforcement: auto
  verbose: false
  reasoning_effort: medium

terminal:
  backend: local
  cwd: .
  timeout: 180

display:
  skin: default
  tool_progress: minimal

security:
  redact_secrets: true

memory:
  memory_enabled: true
  user_profile_enabled: true

stt:
  enabled: false

tts:
  enabled: false
"@
Set-Content -Path (Join-Path $HermesHome "config.yaml") -Value $ConfigContent -Encoding UTF8

# ===== 6. 创建 start-hermes.bat =====
$BatContent = @'
@echo off
title Hermes Agent 便携版
color 0A
cls

echo =======================================================
echo   Hermes Agent 便携版
echo   即插即用 - 无需安装
echo =======================================================
echo.

set USB_DRIVE=%~d0
set HERMES_ROOT=%USB_DRIVE%\HermesAgent

if not exist "%HERMES_ROOT%\" (
    echo [错误] 找不到 HermesAgent 目录！
    pause
    exit /b 1
)

set HERMES_HOME=%HERMES_ROOT%\hermes_home
set PATH=%HERMES_ROOT%\python;%HERMES_ROOT%\python\Scripts;%PATH%
set PYTHONIOENCODING=gbk

set KEY_CHECK=0
if exist "%HERMES_HOME%\.env" (
    findstr /B "DEEPSEEK_API_KEY=" "%HERMES_HOME%\.env" | findstr /V /C:"DEEPSEEK_API_KEY=sk-xxxx" >nul 2>&1
    if not errorlevel 1 set KEY_CHECK=1
)
if not "%KEY_CHECK%"=="1" (
    echo.
    echo [提示] 还没配置 API Key
    echo        首次使用请先双击 set-api-key.bat 配置
    echo.
    pause
)

echo 正在启动 Hermes Agent ...
echo 配置目录: %HERMES_HOME%
echo.
echo 插上即用 - 所有数据保存在U盘上
echo.
echo ========================================================

%HERMES_ROOT%\python\python.exe -m hermes_cli.main

chcp 936 >nul 2>&1

echo.
echo Hermes 已退出
pause
'@
$bytes = [System.Text.Encoding]::GetEncoding(936).GetBytes($BatContent)
[System.IO.File]::WriteAllBytes((Join-Path $DestRoot "start-hermes.bat"), $bytes)  # GBK (ANSI) + CRLF

# ===== 7. 创建 set-api-key.bat 快速配置工具 =====
$SetKeyBat = @'
@echo off
title Hermes Agent 配置 API Key
cls

echo =======================================================
echo   配置 Hermes API Key
echo =======================================================
echo.

set HERMES_ROOT=%~d0\HermesAgent

if not exist "%HERMES_ROOT%\" (
    echo [错误] 找不到 HermesAgent 目录！
    pause
    exit /b 1
)

echo 选择 API 供应商：
echo.
echo 1) DeepSeek（默认，便宜中文好）
echo    注册: https://platform.deepseek.com/api_keys
echo.
echo 2) OpenRouter（支持200+模型）
echo    注册: https://openrouter.ai/keys
echo.
echo 3) Google Gemini（免费，支持看图）
echo    注册: https://aistudio.google.com/apikey
echo.
set /p CHOICE="请选择 1/2/3 [默认1]: "

if "%CHOICE%"=="" set CHOICE=1
if "%CHOICE%"=="1" (
    set KEY_NAME=DEEPSEEK_API_KEY
) else if "%CHOICE%"=="2" (
    set KEY_NAME=OPENROUTER_API_KEY
) else if "%CHOICE%"=="3" (
    set KEY_NAME=GOOGLE_API_KEY
) else (
    echo 无效选择！
    pause
    exit /b 1
)

echo.
echo 请粘贴你的 %KEY_NAME%
set /p USER_KEY="API Key: "

if "%USER_KEY%"=="" (
    echo API Key 不能为空！
    pause
    exit /b 1
)

> "%HERMES_ROOT%\hermes_home\.env" (
    echo %KEY_NAME%=%USER_KEY%
    if "%KEY_NAME%"=="DEEPSEEK_API_KEY" echo DEEPSEEK_BASE_URL=https://api.deepseek.com
)
echo.
echo OK - API Key 已保存！
echo 现在双击 start-hermes.bat 即可启动
echo.
pause
'@
$bytes = [System.Text.Encoding]::GetEncoding(936).GetBytes($SetKeyBat)
[System.IO.File]::WriteAllBytes((Join-Path $DestRoot "set-api-key.bat"), $bytes)  # GBK (ANSI) + CRLF

# ===== 8. 创建 README =====
$Readme = @"
Hermes Agent 便携版 —— U盘即插即用
======================================

无需安装，插上U盘就能用 AI 编程助手。


快速开始（给你的同事）
--------------------

1. 插上 U盘
2. 双击 start-hermes.bat
3. 第一次用 → 先选供应商并填 API Key
4. 在终端里输入 hermes 开始聊天

或者用快速配置工具：
   双击 set-api-key.bat
   选供应商 → 粘贴 API Key → 完成


配置说明
--------

API Key 放在 hermes_home/.env 里
模型和providers在 hermes_home/config.yaml 里

常用命令：
  hermes           启动交互会话
  hermes model     切换模型/供应商
  hermes chat -q "写一个Python排序"  单次提问
  hermes doctor    检查环境
  hermes setup     运行设置向导


这个 U盘里有什么
--------------

  HermesAgent/
  ├── python/               # 可移植 Python 3.11
  ├── hermes_home/          # Hermes 配置和用户数据
  │   ├── config.yaml       # 配置文件
  │   ├── .env              # API Key（需要你填）
  │   ├── sessions/         # 会话历史
  │   └── skills/           # 技能
  ├── start-hermes.bat      # 启动 Hermes（双击这个）
  ├── set-api-key.bat       # 快速配置 API Key
  └── README.txt            # 本文件


支持的供应商
-----------

- OpenRouter (推荐) — 200+ 模型，一个 API Key 搞定
  https://openrouter.ai/keys

- DeepSeek — 便宜，不到1分钱一次对话
  https://platform.deepseek.com/api_keys

- Google Gemini — 免费，还能看图
  https://aistudio.google.com/apikey

- Anthropic Claude — 编程能力强
  https://console.anthropic.com/

- 更多：在 Hermes 里运行 hermes model 查看


注意事项
--------

1. U盘需要至少 2GB 可用空间
2. 同事的电脑需要能访问 API 服务器的网络
3. 所有数据保存在 U盘上，拔出即带走
4. 建议用 USB 3.0 以上的 U盘，速度更快
"@
Set-Content -Path (Join-Path $DestRoot "README.txt") -Value $Readme -Encoding UTF8

# ===== 完成 =====
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   ✓ 构建完成！" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "目录结构:" -ForegroundColor Yellow
Write-Host "  $DestRoot"
Write-Host "  ├── python\          (可移植 Python $(& $PythonExe --version 2>&1))"
Write-Host "  ├── hermes_home\     (Hermes 配置目录)"
Write-Host "  │   ├── config.yaml  (已预配置)"
Write-Host "  │   └── .env         (模板 - 需要填 API Key)"
Write-Host "  ├── start-hermes.bat (双击启动)"
Write-Host "  ├── set-api-key.bat  (快速配置 API Key)"
Write-Host "  └── README.txt       (使用说明)"
Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 把整个 HermesAgent 文件夹复制到 U盘根目录"
Write-Host "  2. 把 U盘插到同事电脑"
Write-Host "  3. 同事双击 start-hermes.bat"
Write-Host "  4. 按提示输入 API Key"
Write-Host "  5. 输入 hermes 开始用！"
Write-Host ""
Write-Host "注意：如果同事电脑没有 winget/git，"
Write-Host "      请在构建电脑上运行此脚本，再复制到 U盘。" -ForegroundColor Yellow
Write-Host ""

---
name: hermes-portable-usb
description: Build a portable Hermes Agent USB drive for Windows - plug-and-play, no installation needed. Uses Windows embeddable Python + GBK-encoded batch files.
version: 1.0.0
author: Bao
tags: [hermes, usb, portable, windows, offline, plug-and-play]
---

# Hermes Agent 便携 U盘

构建一个即插即用的 Hermes Agent U盘。同事插上 U盘 → 配 API Key → 直接开用，无需安装任何东西。

## 工作原理

- **Windows embeddable Python**（免安装，<20MB）
- `pip install hermes-agent` 到 U盘的可移植 Python 上
- `HERMES_HOME` 环境变量指向 U盘内目录，所有配置/会话/技能都存 U盘
- 启动 bat 用 `%~d0` 自动检测 U盘盘符（D:/E:/F: 都行）
- 用 `python -m hermes_cli.main` 代替 `hermes.exe`，避免 pip 启动器的路径硬编码问题

## 使用流程

### 构建端（有网的 Windows 电脑）

1. 运行 `build-hermes-usb.ps1 [-UsbPath "D:\"]`
2. 脚本自动下载 Python、pip install hermes-agent、生成配置文件
3. 把生成的 `HermesAgent\` 文件夹复制到 U盘根目录

### 用户端（同事的电脑）

1. 插 U盘
2. 双击 `set-api-key.bat` → 选择供应商 → 粘贴 API Key
3. 双击 `start-hermes.bat` → 直接开用

## 关键编码规则

| 文件 | 编码 | 原因 |
|------|------|------|
| `.bat` 文件 | **GBK (ANSI)** - CP936 | cmd.exe 原生编码，不乱码不卡 BOM |
| `.env` 文件 | **UTF-8 无 BOM** | 环境变量解析不能有 BOM |
| `config.yaml` | **UTF-8 with BOM** | YAML 解析兼容 |
| `README.txt` | **UTF-8 with BOM** | 记事本打开正确 |

## 构建脚本要点

脚本位于 `build-hermes-usb.ps1`（PowerShell 脚本，在 Windows 上运行）：

### 下载
```powershell
# Python 3.11 embeddable（备用 3.12）
$PythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip -UseBasicParsing
```

### 启用 site-packages
解压后修改 `python*._pth`，把 `#import site` 改成 `import site`。

### 安装依赖
```powershell
# 下载 get-pip.py 并安装
& $PythonExe get-pip.py --no-warn-script-location
# 安装 Hermes Agent（核心依赖即可）
& $PipExe install "hermes-agent" --no-warn-script-location
```

### 写入 bat 文件（必须 GBK + CRLF）
```powershell
$bytes = [System.Text.Encoding]::GetEncoding(936).GetBytes($BatContent)
[System.IO.File]::WriteAllBytes((Join-Path $DestRoot "start-hermes.bat"), $bytes)
```

### 写入 .env（必须 UTF-8 无 BOM）
```powershell
[System.IO.File]::WriteAllText((Join-Path $HermesHome ".env"), $EnvContent)
```

## Pitfalls

### 1. pip 启动器硬编码路径
`pip install` 生成的 `hermes.exe` 会把 Python 路径写死在 exe 里。U盘换盘符后报错：
```
Fatal error in launcher: Unable to create process using '"D:\...\python.exe" "F:\...\hermes.exe"'
```
**修复：** 不使用 `hermes.exe`，改用 `python -m hermes_cli.main`

### 2. UTF-8 BOM 导致 cmd 报错
bat 文件有 UTF-8 BOM（`EF BB BF`）时，cmd.exe 会把它当成命令：
```
'锘緻echo' 不是内部或外部命令
```
**修复：** bat 文件必须用 GBK 编码，不要 BOM

### 3. chcp 65001 + echo 中文兼容问题
`chcp 65001` 切到 UTF-8 后，`echo` 某些中文行会被当成命令执行。部分 Windows 版本的 cmd.exe 有这 bug。
**修复：** 不用 `chcp 65001`，保持系统默认编码（中文 Windows 是 936/GBK），同时设 `PYTHONIOENCODING=gbk`

### 4. Hermes 退出后控制台编码被改
Hermes Agent（Python）可能把控制台切到 UTF-8。退出后 echo 中文乱码。
**修复：** Hermes 退出后补 `chcp 936 >nul 2>&1`

### 5. .env 有 BOM 导致 Key 读不到
`Set-Content -Encoding UTF8` 写入的 .env 带 BOM，环境变量解析器会把 key name 当成 `\ufeffDEEPSEEK_API_KEY`。
**修复：** 用 `[System.IO.File]::WriteAllText()` 写入（.NET 默认 UTF-8 无 BOM）

### 6. 换行必须是 CRLF
Linux 风格的 LF 换行在 cmd.exe 中可能解析失败。bat 文件中必须用 `\r\n`。

## U盘目录结构

```
HermesAgent/
├── python\               ← 可移植 Python + Hermes Agent
│   ├── python.exe
│   └── Lib\site-packages\hermes_cli\
├── hermes_home\          ← 所有配置和用户数据
│   ├── config.yaml       ← 预配置
│   ├── .env              ← API Key（用户填）
│   ├── sessions\
│   └── skills\
├── start-hermes.bat      ← 一键启动
├── set-api-key.bat       ← 配置 API Key
└── README.txt
```

## 参考文件

构建脚本 `build-hermes-usb.ps1` 是完整的自动化工具，位于同目录下的 `scripts/` 文件夹。

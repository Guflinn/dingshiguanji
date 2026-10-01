# 定时关机

Windows 定时电源工具：定时 **关机 / 重启 / 睡眠 / 休眠 / 注销 / 锁屏**，苹果风浅色界面，支持高 DPI 与窗口等比缩放。

## 下载（免安装）

直接下载单文件版：**[dingshiguanji.exe](https://github.com/Guflinn/dingshiguanji/releases/download/v1.0.0/dingshiguanji.exe)**（约 29.5 MB，Windows 10/11 x64，不需要 Python）

全部版本见 [Releases](https://github.com/Guflinn/dingshiguanji/releases)。
二进制不进仓库历史，因此仓库里只有源码。

## 功能

- 两种定时方式：倒计时（时/分/秒）与指定时刻（如 23:30，已过则自动跨天）
- 六种动作：关机、重启用系统 `shutdown /t` 定时（程序退出也照样执行）；睡眠 / 休眠 / 注销 / 锁屏由程序计时（需保持运行）
- 关机前提醒：可提前 30 秒 / 1 分钟 / 5 分钟弹窗，支持「延后 5 分钟 / 立即执行 / 取消」
- 自动记住上次的动作、模式、数值与窗口大小
- 测试模式：设置环境变量 `DSH_TEST_MODE=1` 后只记录将要执行的命令，不真正执行

## 直接运行

需要 Python 3，装 Pillow 可获得抗锯齿圆角（没有则退化成多边形圆角）：

```
python ds_shutdown.py
```

或双击 `启动定时关机.bat`。

## 打包成单文件 exe

```powershell
.\打包.ps1
```

脚本用 PyInstaller 打包，末尾会用 `icacls /setintegritylevel Medium` 修正完整性级别——工作区被标记为「低完整性」时，生成的 exe 无法在 %TEMP% 解压自身（表现为弹窗 Could not create temporary directory!）。

`打包.ps1` 默认使用 PATH 中的 `python`，可用环境变量 `DSH_PYTHON` 指定解释器路径。

依赖可离线获取：`python fetch_deps.py` 会从清华镜像直接下载 wheel 并解压到 `pylibs/`（绕开 pip）。

## 文件说明

| 文件 | 作用 |
|---|---|
| `ds_shutdown.py` | 主程序（tkinter UI + 定时逻辑） |
| `make_icon.py` | 生成 `icon.ico`（电源符号 + 时钟） |
| `fetch_deps.py` | 下载 PyInstaller 等依赖到 `pylibs/` |
| `定时关机.spec` | PyInstaller 配置 |
| `打包.ps1` / `启动定时关机.bat` | 打包脚本 / 启动脚本 |

> 本仓库只收录源码与图标。`定时关机.exe`（约 30 MB）以及 `build/`、`pylibs/`、`__pycache__` 等构建产物未纳入版本管理。

由 DeepSeek Harness 会话生成。

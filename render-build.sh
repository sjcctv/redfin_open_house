#!/bin/bash
# -------------------------------
# render-build.sh for Render
# Compatible with Linux
# -------------------------------

# 遇到错误就停止
set -e

# 确保脚本是 LF 换行（如果在 Windows 上写过）
# 如果还没转换，先在本地运行: dos2unix render-build.sh

echo ">>> Upgrade pip"
pip install --upgrade pip

echo ">>> Install Python dependencies"
pip install -r requirements.txt

echo ">>> Install Playwright browsers"
# 如果你用 playwright 1.40+，这个命令安装 chromium
playwright install chromium

echo ">>> Build complete!"

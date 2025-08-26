#!/usr/bin/env bash
set -eux

# 删除 Render 的旧 Playwright 缓存
rm -rf /opt/render/.cache/ms-playwright || true

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Chromium 到虚拟环境
playwright install --with-deps chromium

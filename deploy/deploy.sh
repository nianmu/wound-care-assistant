#!/usr/bin/env bash
# ============================================
# 阿里云 2C2G 一键部署脚本
# 在服务器上以常规用户执行（建议 ubuntu）
# ============================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/wound-care-assistant}"
SERVER_USER="${USER:-$(whoami)}"

echo "==> [1/6] 创建目录"
mkdir -p "$APP_DIR"

echo "==> [2/6] 上传代码（请先在本机打包上传）"
# 说明：执行本脚本前，先把项目代码（排除 .venv/node_modules/chroma_db/data）
# 上传到 $APP_DIR。可用 scp 或 rsync，例如：
#   rsync -av --exclude .venv --exclude node_modules --exclude chroma_db --exclude data \
#         ./ wound-care-assistant/ 服务器IP:$APP_DIR/

echo "==> [3/6] 开启 Swap（内存保障，2G）"
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  echo "    Swap 2G 已启用"
else
  echo "    Swap 已存在，跳过"
fi

echo "==> [4/6] 安装系统依赖"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip nginx supervisor

echo "==> [5/6] 创建 venv 并安装后端依赖"
cd "$APP_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> [6/6] 配置 Supervisor + Nginx"
sudo ln -sf "$APP_DIR/deploy/supervisor.conf" /etc/supervisor/conf.d/wound-care.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart wound-api

if [ -f "$APP_DIR/deploy/nginx.conf" ]; then
  sudo ln -sf "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/wound-care
  sudo ln -sf /etc/nginx/sites-available/wound-care /etc/nginx/sites-enabled/wound-care
  sudo nginx -t
  sudo systemctl reload nginx
fi

echo ""
echo "✅ 部署完成！"
echo "   后端:   http://127.0.0.1:8000/health"
echo "   前端:   需要先将 frontend/dist/build/h5 内容放到 /var/www/wound-care"
echo "   （本机构建: cd frontend && npm run build:h5）"
echo "   查看日志: sudo tail -f /var/log/wound-care/api.log"
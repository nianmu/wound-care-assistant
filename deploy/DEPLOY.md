# 部署说明（阿里云 2C2G）

## 一、在开发机打包

```bash
# 1. 构建前端 H5 产物（产物在 frontend/dist/build/h5/）
cd frontend && npm run build:h5

# 2. 准备部署目录（排除本地运行产物）
#    需要的文件：
#    - app/  models.yaml  requirements.txt  deploy/
#    - frontend/dist/build/h5/*  → 放到服务器 /var/www/wound-care/
#    - .env（含真实 Key）
```

## 二、上传服务器

```bash
# 把项目传到 /opt/wound-care-assistant（rsync 排除本地依赖）
rsync -av --exclude '.venv' --exclude 'node_modules' --exclude 'chroma_db' \
      --exclude 'data/raw/*.txt' --exclude 'frontend/dist' \
      ./ user@服务器IP:/opt/wound-care-assistant/

# 单独上传前端产物
mkdir -p /var/www/wound-care
rsync -av frontend/dist/build/h5/ user@服务器IP:/var/www/wound-care/
```

## 三、执行部署脚本

```bash
ssh user@服务器IP
cd /opt/wound-care-assistant
chmod +x deploy/deploy.sh
./deploy/deploy.sh        # 开启 Swap、装依赖、配 Supervisor + Nginx
```

## 四、验证

```bash
curl http://127.0.0.1:8000/health                # 后端 OK
curl http://服务器IP/healthz                      # Nginx 转发 OK
curl http://服务器IP/                             # 前端页面 OK
sudo tail -f /var/log/wound-care/api.log         # 后端日志
```

## 五、日常管理

```bash
sudo supervisorctl status wound-api        # 查看状态
sudo supervisorctl restart wound-api       # 重启后端
sudo systemctl reload nginx                # 重载前端静态配置
sudo nginx -t                              # 检查 Nginx 配置语法
```

## 安全提示

- `.env` 含 API Key，**切勿**上传到公开仓库；服务器上记得 `chmod 600 .env`
- 生产建议用 HTTPS（Nginx 配置证书），并用域名替换 `server_name _`
- 如开放公网，建议在 `/api/ask`、`/api/upload` 前加简单访问控制（Nginx Basic Auth 即可，单用户场景够用）
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

- `.env` 含 API Key 与 `JWT_SECRET`，**切勿**上传到公开仓库；服务器上记得 `chmod 600 .env`
- 生产建议用 HTTPS（Nginx 配置证书），并用域名替换 `server_name _`
- 如开放公网，建议在 `/api/ask`、`/api/upload` 前加简单访问控制（Nginx Basic Auth 即可，单用户场景够用）

## 六、账户体系部署要点（2026-09-01 起）

1. 服务器 `.env` 必须新增 `JWT_SECRET`（**缺失后端启动即报错**）：
   ```bash
   echo "JWT_SECRET=$(openssl rand -hex 32)" >> /opt/wound-care-assistant/.env
   echo "JWT_EXPIRES_DAYS=7" >> /opt/wound-care-assistant/.env
   chmod 600 /opt/wound-care-assistant/.env
   supervisorctl restart wound-api
   ```
2. 旧库（data/exam.db）**自动升级**：`_migrate_schema` 加 user_id 列 + 重建 question_stats 复合主键；历史成绩/错题在**首个注册用户**注册时自动归入（`migrate_legacy_to_user`）
3. 考试模块接口需登录（`Authorization: Bearer <JWT>`）；问答/文档类不强制

## 七、HTTPS 切换（域名 nianmu.top 备案通过后执行，约 10 分钟）

> 过渡期：域名备案中，暂时公网 IP + HTTP 明文访问。账户体系（B 模式）有密码，
> 备案通过后**务必尽快切换到 HTTPS**（过渡期风险仅限家庭自用场景）。

```bash
# 1. 阿里云控制台 → SSL 证书 → 申请免费证书（域名 nianmu.top，DNS 验证）
# 2. 下载 nginx 版 → 上传两文件到服务器（示例路径）
#    /etc/nginx/ssl/nianmu.top.pem
#    /etc/nginx/ssl/nianmu.top.key

# 3. 启用预留的 ssl 配置（模板在 deploy/nginx-ssl.conf，需填证书路径）
cp deploy/nginx-ssl.conf /etc/nginx/conf.d/wound-care-ssl.conf
#    —— 按模板注释修改 ssl_certificate / ssl_certificate_key / server_name
nginx -t && systemctl reload nginx

# 4. 验证
curl -I https://nianmu.top                # 200
# 80 端口 server 已含 301 → https 全站跳转；/api 反代与 timeout 配置与 http 一致
```
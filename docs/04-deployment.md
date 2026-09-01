# 部署与运维 — 阿里云 2C2G

> 部署脚本见 `deploy/`（deploy.sh / supervisor.conf / nginx.conf / DEPLOY.md）。本文是运维手册。

## 1. 部署架构

```
阿里云 2C2G（Ubuntu）
├── Nginx (:80)
│   ├── 托管前端静态文件 /var/www/wound-care（H5 构建产物）
│   ├── 反代 /api/* → 127.0.0.1:8000
│   ├── /healthz → 后端 /health
│   └── client_max_body_size 20m（教材上传）
└── Uvicorn (:8000，Supervisor 守护，1 worker)
    ├── app/（RAG + 考试）
    ├── data/raw/*.txt（教材）
    ├── chroma_db/（向量库）
    ├── data/exam.db（题库/成绩）
    └── .env（API Key）
```

**关键原则**：服务器不装 Node（前端是纯静态）、不装解析库（PDF/OCR 在开发机）、单 worker 单进程。

## 2. 部署步骤

参考 `deploy/DEPLOY.md` 全流程，核心：

```bash
# 开发机
cd frontend && npm run build:h5          # 产物 dist/build/h5/
rsync -av --exclude '.venv' --exclude 'node_modules' --exclude 'chroma_db' \
      --exclude 'data/raw/*.txt' --exclude 'frontend/dist' \
      ./ user@服务器:/opt/wound-care-assistant/
rsync -av frontend/dist/build/h5/ user@服务器:/var/www/wound-care/

# 服务器
cd /opt/wound-care-assistant && chmod +x deploy/deploy.sh && ./deploy/deploy.sh
# 脚本自动：开 Swap 2G → 装依赖 → venv → pip install → supervisor → nginx
```

`.env` 需上传（含真实 Key），且 `chmod 600 .env`。

## 3. Swap（2C2G 内存保障，必需）

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 4. 日常管理命令

```bash
sudo supervisorctl status wound-api      # 状态
sudo supervisorctl restart wound-api     # 重启后端
sudo supervisorctl tail wound-api        # 日志
sudo nginx -t && sudo systemctl reload nginx   # 重载 Nginx
sudo tail -f /var/log/wound-care/api.log # 后端日志
```

## 5. 升级/更新流程

```bash
# 后端代码变更
rsync app/ deploy/ models.yaml requirements.txt 到服务器
sudo supervisorctl restart wound-api

# 前端变更
开发机 npm run build:h5 → rsync 产物 → 无需重启（静态）
```

## 6. 已知坑与规避（本机/开发示例沉淀）

| 坑 | 规避 |
| :-- | :-- |
| whenix 依赖：chromadb 0.5 Windows 无 wheel | 用 **1.5.9**（自带 hnsw，Win/Linux 通吃；API 兼容） |
| PowerShell `-Form` 上传锁文件/500 | 用 curl / requests / Python；前端 uni-app 上传无此问题 |
| onnxruntime-gpu 1.29 需 CUDA13（本机 12.3） | 用 **onnxruntime-directml**（DML） |
| uv 全局缓存 D 盘权限故障 | `UV_CACHE_DIR` 指工作区 `.uv-cache`（本机特例） |
| choco 无管理员装不了 tesseract | 用户以管理员运行（沙箱/受限用户写不了 C） |
| uni-app dev 偶发不改 methods | 重启 `npm run dev:h5` |

## 7. 安全提示

- 公网建议：Nginx Basic Auth（单用户场景够用）+ HTTPS + 域名替换 `server_name _`
- `.env` 含 Key：gitignore 已排除；服务器 chmod 600
- 知乎/开放公网前：`/api/*` 建议加访问控制（ask/upload/exam 均可被外部调用产生费用）
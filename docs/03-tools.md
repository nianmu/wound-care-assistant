# 文档转换工具 — tools/

> **原则**：PDF/EPUB 解析与 OCR 全部在开发机完成，服务器只收 UTF-8 纯文本（2C2G 跑不动解析）。

## 1. 核心转换链（开发机 → txt 带页码标记）

```
PDF/EPUB（开发机）──► tools 脚本 ──► UTF-8 txt（含 @@PAGE:N@@ 标记）──► 上传服务器
```

页码标记格式（跨模块协议，详见 [01-backend/ingestion.md](01-backend/ingestion.md)）：

```
@@PAGE:1@@
（第1页内容）
@@PAGE:2@@
（第2页内容）
```

## 2. 脚本清单

| 脚本 | 用途 | 依赖 |
| :-- | :-- | :-- |
| `convert_pdf.py` | 文字版 PDF → txt（PyMuPDF 提取，带页码） | pymupdf |
| `convert_pdf_ocr.py` | 扫描版 PDF → txt（Tesseract OCR，CPU 兜底） | pymupdf + tesseract(chi_sim) |
| `convert_pdf_gpu.py` | **推荐**：扫描版 → txt（RapidOCR GPU，带页码） | pymupdf + rapidocr + onnxruntime-directml |
| `convert_epub.py` | EPUB → txt（zip+BeautifulSoup，带块序号标记） | ebooklib→改为 zip+bs4、lxml |
| `batch_ocr.py` | 批量 OCR 多本（data/raw 下按关键词匹配） | 复用 convert_pdf_gpu |
| `convert_dragdrop.bat` | **一键拖放**：把文件拖到 bat 上自动转 | 调上面 Python 脚本 |

## 3. GPU OCR（性能关键）

- **RapidOCR + onnxruntime-directml**：本机 RTX 3050 实测约 **1.1~1.8 秒/页**，中文质量优于 Tesseract
- 实测：3 本教材 1017 页共 **29.7 分钟**（Tesseract CPU 需 1.5h+）
- 通过 `params={"EngineConfig.onnxruntime.use_dml": True}` 启用 DML（Windows 免 CUDA 环境）
- 失败自动回退 Tesseract（`_find_tesseract` 探测 PATH + 常见安装路径）

## 4. 数据库/知识库导入

### 方式 A：上传 API（推荐，带索引）

```bash
# pandas-free 方式：任一支持以下上传的 HTTP 客户端
curl -X POST -F "file=@教材.txt" http://127.0.0.1:8000/api/upload
# 或前端「上传」页（还能看到已索引情况）
```

方式 B：手工放文件——直接把 txt 放到服务器 `data/raw/`，但**不会自动索引**，需额外触发（当前无批量索引 API；默认走上传页）。

## 5. 各类型处理要点

| 类型 | 处理 | 注意 |
| :-- | :-- | :-- |
| 文字版 PDF | convert_pdf.py | 快；无 OCR 负担 |
| 扫描版 PDF | convert_pdf_gpu.py | 需 GPU 依赖 + 页码标记自动带 |
| EPUB | convert_epub.py | 无物理页码，用内容块序号 @@PAGE:N@@ |
| 混合（部分页有文字） | OCR 脚本自动跳过有文字层页 | 已实现 |

## 6. 修改指南 / 已知注意

- **改页码标记格式**：必须同步 tools 生成端与 `app/ingestion/loader.py` 消费端
- GPU 不可用：装 `onnxruntime-directml`（DML 版）；CUDA 环境勿装 onnxruntime-gpu 1.29 新版（要求 CUDA 13，本机 12.3 不匹配——**已踩过坑，见下**）
- Tesseract 兜底：Windows 需管理员装（choco），chi_sim.traineddata 放 tessdata 目录；沙箱环境无法代装（C 盘写权限）
- 本机 uv 缓存：`UV_CACHE_DIR` 指向工作区 `.uv-cache`（全局 D 盘缓存曾权限故障）——属本机特有问题，见 [04-deployment.md](04-deployment.md) 备注
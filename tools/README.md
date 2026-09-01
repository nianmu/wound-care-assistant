# 本地文档转换工具（开发机运行）

**设计原则：PDF/EPUB 解析全部在开发机完成，服务器只接收 UTF-8 txt（保持 2C2G 轻量）。**

## ⭐ 最省事的方式：拖放转换

把 PDF / EPUB 文件**直接拖到 `convert_dragdrop.bat` 上松手**即可：

- 文字版 PDF → 自动提取文字
- 扫描版 PDF → 自动尝试 OCR（需先装 Tesseract 中文包，见下）
- EPUB → 自动提取正文

转换结果与源文件同目录（同名 .txt），然后在前端「上传」页上传即可。

## 命令行方式

```bash
# 文字型 PDF
python tools/convert_pdf.py 造口护理学.pdf                 # 输出同目录 .txt
python tools/convert_pdf.py 造口护理学.pdf data/raw/       # 指定输出目录

# 扫描版 PDF（OCR）——需先安装 Tesseract 中文包
#   下载: https://github.com/UB-Mannheim/tesseract/wiki（安装时勾选 chi_sim）
python tools/convert_pdf_ocr.py 老教材扫描版.pdf [输出] [dpi=300]

# EPUB
python tools/convert_epub.py 造口护理学.epub
```

## 批量转换（PowerShell）

```bash
Get-ChildItem *.pdf | ForEach-Object { python tools/convert_pdf.py $_.FullName data/raw/ }
```

## 注意事项

- 转换出的 txt 必须是 **UTF-8 编码**（脚本默认已是）
- 扫描版 dpi 默认 300：清晰度差的扫描件可试 400（更慢更准）
- 转换在开发机做，**不要在服务器上跑这些脚本**
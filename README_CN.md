# Chou (瞅) - 学术论文 PDF 重命名工具

一个 Python 工具，通过从 PDF 内容中提取标题、作者和年份信息，自动将学术论文 PDF 重命名为引文格式的文件名。

## 功能特点

- 使用字体大小分析从 PDF 首页提取标题和作者
- **OCR 支持** - 支持扫描版 PDF（5 种 OCR 后端可选）
- 使用 10 种不同策略提取出版年份（支持中英文）
- **中文姓名处理** - 中文作者自动使用全名（如"张三"而非"张"）
- **中文学位论文支持** - 自动识别"论文题目"、"作者姓名"等标签字段
- 多种作者格式选项
- 预览模式（dry-run）确保安全
- 处理作者名中的特殊字符和 Unicode
- 记录所有操作并导出 CSV 结果

## 环境要求

- Python >= 3.10
- PyMuPDF（必需）
- OCR 后端（可选，用于扫描版 PDF）

## 安装

### 从 PyPI 安装

```bash
pip install chou
```

### 从源码安装

```bash
git clone https://github.com/cycleuser/Chou.git
cd Chou
pip install -e .
```

### 安装 OCR 支持

根据需要选择一个或多个 OCR 后端：

```bash
# 安装所有 OCR 后端
pip install -e ".[ocr-surya,ocr-paddle,ocr-rapid,ocr-easy,ocr-tesseract]"

# 或单独安装特定后端：
pip install surya-ocr              # Surya - 准确率最高，基于 Transformer（推荐）
pip install paddleocr paddlepaddle # PaddleOCR - 中文支持好
pip install rapidocr-onnxruntime   # RapidOCR - 轻量级，速度快
pip install easyocr                # EasyOCR - 使用简单
pip install pytesseract Pillow     # Tesseract - 经典 OCR
```

## 快速开始

安装后，`chou` 命令即可使用：

```bash
# 预览更改（默认模式）
chou --dir /path/to/papers --dry-run

# 实际执行重命名
chou --dir /path/to/papers --execute

# 显示版本
chou --version
```

## 使用方法

```bash
chou [选项]
```

### 命令行选项

| 选项 | 简写 | 说明 |
|------|------|------|
| `--dir DIR` | `-d` | 包含 PDF 文件的目录（默认：当前目录） |
| `--dry-run` | `-n` | 仅预览，不实际重命名（默认：True） |
| `--execute` | `-x` | 实际执行重命名 |
| `--format FMT` | `-f` | 作者名格式（见下表） |
| `--num-authors N` | `-N` | n_* 格式使用的作者数量（默认：3） |
| `--recursive` | `-r` | 递归处理子目录（默认：True） |
| `--no-recursive` | | 仅处理指定目录 |
| `--ocr-engine` | | 指定 OCR 引擎（默认：自动检测） |
| `--no-ocr` | | 禁用 OCR 回退 |
| `--output FILE` | `-o` | 导出结果到 CSV 文件 |
| `--log-file FILE` | `-l` | 日志文件路径 |
| `--verbose` | `-v` | 详细输出 |

### 作者格式选项 (`-f`)

| 格式 | 英文论文示例 | 中文论文示例 |
|------|--------------|--------------|
| `first_surname` | `Wang et al. (2023) - Title.pdf` | `张三 (2023) - 标题.pdf` |
| `first_full` | `Weihao Wang et al. (2023) - Title.pdf` | `张三 (2023) - 标题.pdf` |
| `all_surnames` | `Wang, Zhang, You (2023) - Title.pdf` | `张三, 李四 (2023) - 标题.pdf` |
| `all_full` | `Weihao Wang, Rufeng Zhang (2023) - Title.pdf` | `张三, 李四 (2023) - 标题.pdf` |
| `n_surnames` | `Wang, Zhang et al. (2023) - Title.pdf` | `张三 et al. (2023) - 标题.pdf` |
| `n_full` | `Weihao Wang, Rufeng Zhang et al. (2023) - Title.pdf` | `张三 et al. (2023) - 标题.pdf` |

**注意：** 对于中文作者，系统会自动使用完整姓名（如"张三"而不是单独的姓"张"），因为单字姓氏在文件名中没有意义。

### 使用示例

```bash
# 使用第一作者全名
chou -d /path/to/papers -f first_full --dry-run

# 使用前 2 位作者的姓氏
chou -d /path/to/papers -f n_surnames -N 2 --dry-run

# 处理并导出结果
chou -d /path/to/papers --execute -o results.csv

# 使用特定 OCR 引擎
chou -d /path/to/papers --ocr-engine rapidocr --dry-run

# 禁用 OCR
chou -d /path/to/papers --no-ocr --dry-run
```

## OCR 支持

对于没有嵌入文字的扫描版 PDF，工具会自动使用 OCR。可用的后端（按优先级排序）：

| 后端 | 安装命令 | 说明 |
|------|----------|------|
| Surya | `pip install surya-ocr` | 准确率最高，基于 Transformer |
| PaddleOCR | `pip install paddleocr paddlepaddle` | 中文支持好 |
| RapidOCR | `pip install rapidocr-onnxruntime` | 轻量级，速度快 |
| EasyOCR | `pip install easyocr` | 使用简单 |
| Tesseract | `pip install pytesseract Pillow` | 经典 OCR |

工具会自动选择最佳可用后端。要禁用特定后端：

```bash
# 禁用 Surya OCR（例如在低内存系统上）
export CHOU_DISABLE_SURYA=1
chou --dry-run
```

## 年份提取策略

工具使用 10 种策略提取出版年份，按置信度排序：

1. **会议+年份** (100): `CVPR 2023`, `NeurIPS'22`, `AAAI-23`
2. **序数届次** (90): `Thirty-Seventh AAAI Conference`
3. **版权声明** (85): `Copyright © 2023`, `版权所有 2023`
4. **发表日期** (80): `Published: 2023`, `发表于 2023`, `收稿日期 2023`
5. **中文年份** (78): `2023年`, `二〇二三年`
6. **arXiv ID** (75): `arXiv:2301.12345`
7. **DOI含年份** (75): `10.1109/CVPR.2023.xxx`
8. **期刊卷期** (70): `Vol. 35, 2023`, `第35卷 2023`
9. **日期格式** (60-65): `March 2023`, `2023年3月`
10. **高频年份** (20-50): 文本中出现最多的年份

## 支持的会议

AAAI, IJCAI, NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, ACL, EMNLP, NAACL, SIGIR, KDD, WWW, CHI, USENIX 等 50+ 个学术会议。

## 中文支持

支持以下中文年份和日期格式：
- 阿拉伯数字年份：`2023年`, `2024年3月`
- 中文数字年份：`二〇二三年`, `二零二四年`
- 出版日期：`发表于`, `出版日期`, `收稿日期`, `录用日期`, `修回日期`, `刊出日期`
- 期刊信息：`第35卷`, `第4期`
- 版权声明：`版权所有`, `版权`
- 学位论文：`论文题目`, `作者姓名`, `指导教师`

## 项目结构

```
Chou/
├── chou/                  # 主包
│   ├── core/             # 核心功能
│   │   ├── processor.py       # PDF 处理
│   │   ├── ocr_extractor.py   # OCR 后端
│   │   ├── author_parser.py   # 作者名解析
│   │   ├── year_parser.py     # 年份提取
│   │   └── filename_gen.py    # 文件名生成
│   ├── cli/              # 命令行界面
│   └── gui/              # 图形界面（可选）
├── tests/                # pytest 测试
├── requirements.txt      # 依赖
├── pyproject.toml        # 包配置
├── README.md             # 英文文档
└── README_CN.md          # 本文件
```

## 图形界面（可选）

可安装图形用户界面：

```bash
pip install chou[gui]
chou-gui
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[test]"

# 运行测试
pytest

# 详细输出
pytest -v
```

## 许可证

MIT License

> 本文记录调研阶段。当时未安装候选工具；后续已完成310页RapidOCR和独立RapidLaTeXOCR实测，见 handbook.md 与 formula-ocr-validation.md。

# 四册中文扫描量级册：本地 OCR 项目核查与执行建议

核查日期：2026-10-18。来源限项目官方仓库、官方文档、官方模型仓库和 PyPI 元数据。没有安装软件、下载模型权重或运行 OCR；仅额外读取了现装 RapidOCR 源码、模型文件大小，并读取 RapidLaTeXOCR 的 11.6 kB wheel 源码。

## 针对当前机器的选择

**立即使用现装 `rapidocr_onnxruntime==1.4.4` 建立全册逐页底稿，保留页图、四点坐标、原始文字和识别分数；数学公式、关系符号、上下标及表格的最终内容须对照原页。** 当前不需要先安装 Paddle、Torch、Transformers 或整套 VLM。

主任务已确认：Windows、Python 3.11.9；现有 `rapidocr_onnxruntime / onnxruntime / cv2 / PIL / numpy / fitz`；没有 Torch、Paddle、Transformers、外部 VLM 配置。RTX 5060 Laptop 标称 8 GB，但当时空闲显存只有约 2.96 GB。实际可用资源比显卡标称容量更适合决定本轮方案。

需要自动转写公式时，最小增量候选是 **RapidLaTeXOCR 0.0.9 在独立 venv 中处理已裁好的公式图片**，其模型文件合计约 170.66 MiB，可走 CPU。它不是全页版面分析器，也不能替代公式视觉复核。需要恢复复杂阅读顺序、表格时，再让 PP-StructureV3 或 MinerU 4.x 对少量难页做第二路解析；先用实页对照证明补缺效果，再决定是否扩大使用。

“全册 OCR 完成”“全文语义已读完”“公式逐项核对完成”应分成三个状态记录，不能互相代替。这是本项目的验收建议，不是任何 OCR 项目提供的保证。

## 项目比较

| 项目与核实版本 | Windows / Python 3.11 | 中文、版面、公式、表格 | 坐标与分数 | 本轮定位 |
|---|---|---|---|---|
| **现装 RapidOCR 旧包 1.4.4** | PyPI 声明 `>=3.6,<3.13`，本机已装 | 中英文文字；没有公式语义、表格结构及完整阅读顺序模型 | 实测源码返回 `[polygon,text,score]`；分数是文本识别分，不是事实正确率 | 全页覆盖和可检索证据底稿，立即复用 |
| **新 RapidOCR 3.10.0** | 声明 `>=3.8,<4`；CPU ONNX 路线 | 更多新 OCR 模型和引擎；仍不能单靠文字 OCR 还原数学/表格结构 | 新 API 为结果对象，可保存 boxes/txts/scores 等；不能照搬旧包 tuple 写法 | 可独立环境做疑难文字对照，不是本轮先决条件 |
| **PaddleOCR 3.7.0 / PP-StructureV3** | `doc-parser` 要求 Python>=3.9；Paddle CPU 官方有 Windows cp311 wheel | 中英文 OCR、版面、阅读顺序、表格、公式；公式模型可选 PP-FormulaNet 系列 | JSON 含页索引、版面类别/score/coordinate、OCR 多边形/rec_scores；可导出 Markdown | 四者中较直接的中文结构化候选，但新增依赖多 |
| **MinerU 4.0.12** | 声明 `>=3.10,<3.15`；官方当前文档列 Windows；快速安装示例推荐 Python3.12 | Basic/Standard/Advanced 分层；复杂文档结构、表格/公式等由所选 tier 和模型决定；Flash 会保留展示公式图而清空其公式内容，不能当完整公式转写 | 当前 MiddleJson/ModelJson 按页保留 block 与几何；不能把 `mineru parse --json` 当 MiddleJson；逐对象 OCR 置信度不可假设普遍存在 | 若批量版面错误明显，可 CPU Basic/Standard 难页抽验；本轮不装 full |
| **Docling 2.140.0** | 声明 Python>=3.10；官方支持 Windows x86_64/arm64 | PDF 版面、表格、文字，可接 RapidOCR；公式须开启 enrichment 并下载额外模型 | DoclingDocument 有 `prov.page_no/bbox`；ConversionResult 有页级/文档级 confidence；标准文本项不应默认都有独立 confidence | 有价值的结构容器，但本机增加 Torch 等成本不合算 |
| **RapidLaTeXOCR 0.0.9** | 声明 `>=3.6,<3.13`；ONNX CPU，不需要 Torch | 仅公式裁图→LaTeX；没有正文、表格、版面分割 | 只返回 `(latex,elapsed)`，不返回公式可信度；坐标由裁图清单管理 | 最轻的可选公式候选生成器 |
| **Pix2Text 1.1.7** | Python3 项目；官方给 Windows 模型缓存目录，具体依赖需独立解析验证 | 中文/英文、公式、版面、表格，支持混排 | 可返回结构/位置；不能把它的所有结果都当成有校准的公式置信度 | 功能全面但当前 wheel 依赖 Torch/Torchvision/Transformers，非轻量增量首选 |

版本与兼容性来源：[旧 RapidOCR PyPI](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/)、[新 RapidOCR PyPI](https://pypi.org/project/rapidocr/3.10.0/)、[PaddleOCR PyPI](https://pypi.org/project/paddleocr/3.7.0/)、[PaddleOCR 安装](https://www.paddleocr.ai/latest/en/version3.x/installation.html)、[Paddle Windows 安装](https://www.paddlepaddle.org.cn/documentation/docs/en/install/pip/windows-pip_en.html)、[MinerU PyPI](https://pypi.org/project/mineru/4.0.12/)、[Docling PyPI](https://pypi.org/project/docling/2.140.0/)、[Docling 官方仓库](https://github.com/docling-project/docling)、[RapidLaTeXOCR PyPI](https://pypi.org/project/rapid-latex-ocr/0.0.9/)、[Pix2Text PyPI](https://pypi.org/project/pix2text/1.1.7/)。

能力和数据契约来源：[RapidOCR 使用文档](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/)、[PP-StructureV3 官方说明](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)、[MinerU 4.x 输出契约](https://github.com/opendatalab/MinerU/blob/master/docs/en/reference/output_files.md)、[Docling 文档模型](https://docling-project.github.io/docling/reference/docling_document/)、[Docling 置信度](https://docling-project.github.io/docling/concepts/confidence_scores/)、[Docling 公式增强](https://docling-project.github.io/docling/usage/enrichments/)、[RapidLaTeXOCR 源码](https://github.com/RapidAI/RapidLaTeXOCR/blob/main/rapid_latex_ocr/main.py)、[Pix2Text 仓库](https://github.com/breezedeus/Pix2Text)。

## 真实下载体积：不要把很小的 wheel 当作完整安装体积

以下 MiB 按 `bytes / 1024 / 1024` 计算；“模型存储 MB”沿用上游表的口径。依赖包、缓存、解压目录、运行内存另算，未做完整安装 dry-run，故不承诺安装总量。

| 对象 | 核实数据 | 含义 |
|---|---:|---|
| RapidOCR 旧包 wheel | 14.22 MiB（PyPI 页面十进制显示14.9 MB） | 本机已装，无新增下载 |
| 旧包本机三模型 | det 4,745,517 B；rec 10,857,958 B；cls 585,532 B；合计15.44 MiB | 读取现装文件确认；其余依赖已有 |
| 新 rapidocr wheel | 26.02 MiB | 不等于所有新模型/所有引擎大小 |
| paddleocr wheel | 约0.14 MiB | 只是入口包；还需推理引擎、PaddleX与所选模型 |
| PaddlePaddle3.3.1 Windows cp311 CPU wheel | 99.93 MiB | PyPI确实存在该 wheel，不是 GPU/CUDA 就绪证明 |
| PP-FormulaNet_plus-S / M / L | 官方模型存储248 / 592 / 698 MB | M/L 对含中文公式的上游指标更高；不能外推本书准确率 |
| MinerU base wheel | 3.51 MiB | 不是完整模型下载 |
| MinerU Basic ONNX | 官方约0.8 GB模型，最低2 GB RAM | CPU可用 |
| MinerU Standard/Advanced ONNX+llama.cpp | 官方约2 GB模型，最低8 GB RAM | CPU可用，官方建议 Vulkan 加速 |
| MinerU full 的额外安装占用 | 官方约多5 GB；GPU路线至少8 GB可用显存、16 GB总内存 | 当时仅2.96 GB空闲显存不满足这条官方建议 |
| Docling package wheel | 元包，近0 MiB | 实际依赖 `docling-slim[standard]`，其中含 Torch/Torchvision 等 |
| Docling CodeFormulaV2 | `model.safetensors` 630,993,616 B，约601.76 MiB | 仅额外公式模型；布局、表格等另算 |
| Docling TableFormer accurate | 212,758,388 B，约202.90 MiB | 仅表格模型；fast另有145,453,276 B |
| RapidLaTeXOCR wheel | 11.6 kB | 权重另下载 |
| RapidLaTeXOCR 四个模型文件 | 178,952,787 B，约170.66 MiB | encoder 89,008,136；decoder 50,952,726；resizer38,967,751；tokenizer24,174 B |
| RapidLaTeXOCR models.zip | 164,016,062 B，约156.42 MiB | 打包下载与四文件下载择一，不要重复下载 |
| Pix2Text mfr公开ONNX两权重 | encoder87,496,990 B＋decoder30,114,937 B，约112.16 MiB | 只是公式权重，不包括布局、检测、文字、表格及Torch依赖 |

体积来源：[PyPI JSON 元数据接口示例](https://pypi.org/pypi/rapidocr_onnxruntime/json)、[PaddlePaddle3.3.1元数据](https://pypi.org/pypi/paddlepaddle/3.3.1/json)、[Paddle公式模型列表](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/model_list.md)、[MinerU官方资源表](https://github.com/opendatalab/MinerU#model-engines-with-extras)、[Docling当前依赖](https://github.com/docling-project/docling/blob/main/pyproject.toml)、[CodeFormulaV2文件](https://huggingface.co/docling-project/CodeFormulaV2/tree/main)、[TableFormer文件](https://huggingface.co/docling-project/docling-models/tree/main/model_artifacts/tableformer)、[RapidLaTeXOCR官方release资产](https://github.com/RapidAI/RapidLaTeXOCR/releases/tag/v0.0.0)、[Pix2Text公开公式权重](https://huggingface.co/breezedeus/pix2text-mfr/tree/main)。字节值由上述官方API本次读取，未下载权重。

## 首选最小可运行实现

本机现装1.4.4的源码已核实：`RapidOCR()`返回二元tuple；每个普通识别项为`[四点坐标,文字,识别分]`；默认过滤掉`score<0.5`的行；`Global.max_side_len=2000`会先缩小过大的图像。`Det.limit_type=min,limit_side_len=736`只在短边不足时放大，不应误称它必定把大页压成736像素。

最小核心调用如下，仅示意接口；完整批处理还应补日志、断点续跑、异常页和源文件SHA-256。这里不需要pip install：

```python
import json
from pathlib import Path
import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR(
    intra_op_num_threads=4,
    inter_op_num_threads=1,
    # 不让高分辨率扫描页先被默认2000上限缩小。
    # 是否保留到此大小应由实页的速度/内存和小字效果决定。
    max_side_len=4096,
)

pdf = fitz.open("input.pdf")
out = Path("ocr_pages")
out.mkdir(exist_ok=True)
for page_idx, page in enumerate(pdf):
    pix = page.get_pixmap(dpi=240, alpha=False, colorspace=fitz.csRGB)
    image_path = out / f"page_{page_idx + 1:04d}.png"
    pix.save(image_path)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])  # 1.4.4的ndarray输入按BGR处理
    # 低分项保留，交给后续复核；不是提高识别精度的承诺。
    rows, elapsed = engine(bgr, text_score=0.0)
    blocks = []
    for index, row in enumerate(rows or []):
        polygon, text, score = row[:3]
        blocks.append({"id": index, "polygon_px": polygon,
                       "text_raw": text, "rec_score": float(score),
                       "review_status": "unreviewed"})
    record = {
        "pdf_page_no": page_idx + 1, "page_idx": page_idx,
        "page_rotation": page.rotation,
        "page_size_pt": [page.rect.width, page.rect.height],
        "render_size_px": [pix.width, pix.height],
        "dpi": 240, "image": str(image_path),
        "engine": "rapidocr_onnxruntime", "engine_version": "1.4.4",
        "blocks": blocks, "elapsed": elapsed,
        "status": "ocr_returned" if rows else "empty_needs_review"
    }
    (out / f"page_{page_idx + 1:04d}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
```

工程建议（本项目判断）：

1. 四册先做页数清单，逐页保存JSON；PDF页码与印刷页码分开。所有页都进入清单，零文本、图片页、目录页也不能省略。
2. 一次一页、一个OCR engine常驻、有限线程。页图保留原始方向/渲染尺寸；正文索引另存UTF-8文本，切勿用Markdown代替坐标底稿。
3. 若某页密集小字，优先从原PDF重新渲染局部300–400dpi并补识别，保留裁图在原页的偏移及缩放关系。不要只把已缩小的PNG放大，丢失细节无法恢复。
4. 原始行序列与整理后的阅读顺序分开保存。多栏、旁注、表格不能只按`y,x`全页排序后当连续正文。
5. 例如`rec_score<0.85`可作为工程复核标记，但这是自定阈值，未经本册标注集校准；高分行也可能错字、漏上下标。
6. 坐标以保存的页图像素为准。需要PDF点坐标时根据实际渲染宽高映射，并记录旋转/裁剪变换；不要只凭DPI硬算且丢弃变换信息。

## 公式复核路线

### 第一层：不增加软件，原图即证据

全页OCR用于检索和定位。公式及符号密集段保留高清裁图，人工/视觉逐项转写，并保存`formula_raw_candidate`、`formula_verified`、`verification_note`。未核对项明确为`unverified`，不能默默改成看似合理的式子。

量级册尤其核对：`∞ / ω / ℵ`、`ℵ_0 / ℵ_1`、`beth / aleph`、`κ`、幂塔、`2^{ℵ_0}`、上下标、`∈ / ε`、`⊂ / ⊆ / ⊊`、`< / ≤`、否定符号、序数/基数写法及“存在/任意”的区别。一般文本OCR对这些字符的分数不能证明数学语义无误。若原图本身无法读清，标`source_illegible`并保留候选，而不是用常识补齐。

### 第二层：RapidLaTeXOCR 的独立公式候选

官方0.0.9 wheel依赖包含`numpy<2.0.0`、`tokenizers>=0.13.2`、ONNX Runtime等。不要为它降级主任务全局NumPy。以下是可选执行命令，本研究未执行：

```powershell
py -3.11 -m venv D:\Codex\research\battle-scaling\handbook-20261018\.venv-formula
& 'D:\Codex\research\battle-scaling\handbook-20261018\.venv-formula\Scripts\python.exe' -m pip install 'rapid_latex_ocr==0.0.9' 'numpy<2'
```

首次构建`LaTeXOCR()`时可能下载缺少的模型。完全离线时预先从官方release取得四个文件，并传入`image_resizer_path / encoder_path / decoder_path / tokenizer_json`。模型默认输入边界672×192、序列512 token，针对分离好的公式图；长公式应适当拆分并保留对应关系。源码返回字符串和耗时，不提供公式score。[依赖](https://github.com/RapidAI/RapidLaTeXOCR/blob/main/requirements.txt)、[构造器和返回值](https://github.com/RapidAI/RapidLaTeXOCR/blob/main/rapid_latex_ocr/main.py)、[模型资产](https://github.com/RapidAI/RapidLaTeXOCR/releases/tag/v0.0.0)。

生成候选后将LaTeX渲染回图片，与裁图逐项对照；优先核对上下标、括号作用域、分数线、集合关系和量词。渲染成功只说明语法可渲染，不说明转写正确。模型一致也不能替代对原图的核对。

### 第三层：难页结构仍有缺口时再升级

**Paddle方案**：独立环境安装`paddlepaddle==3.3.1`和`paddleocr[doc-parser]==3.7.0`，先走CPU；使用`PPStructureV3(device="cpu",use_doc_unwarping=False,use_doc_orientation_classify=False)`并保存JSON。公式需要Paddle可支持的引擎；官方PP-Structure文档明确ONNXRuntime路线目前须关闭公式识别，不能因为本机已有ONNX就声称完整公式管线可立即运行。将少量真实难页的漏块、阅读顺序、表格结构和公式错误与基线比较；不是只看示例截图。[官方安装](https://www.paddleocr.ai/latest/en/version3.x/installation.html)、[官方PP-StructureV3](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)。

**MinerU方案**：4.x是当前体系，不能沿用旧版`mineru -p ... -o ... -b pipeline`经验。独立环境的基本入口为`pip install "mineru==4.0.12"`；本地模型可用`mineru-kit models download --tier basic`与`mineru-kit models verify --tier basic`管理。执行具体解析前读取所装版本help，使用`mineru-kit parse`或Python ParseResult保存中间JSON及图片包。`mineru parse --json`是命令响应，不是可直接反序列化的MiddleJson。当前空闲显存不适合full；CPU Basic有约0.8GB模型成本，CPU Standard约2GB且最低8GB RAM，实际可用内存仍需主任务核实。Flash不作为本项目完整阅读/公式转写终稿。[官方安装和资源表](https://github.com/opendatalab/MinerU)、[输出协议](https://github.com/opendatalab/MinerU/blob/master/docs/en/reference/output_files.md)。

**Docling方案**：需要更强统一文档结构时可选，但它的标准元包会引入Torch等，不能认为“pip wheel很小所以轻”。可连接新RapidOCR指定本地模型；公式增强默认关闭。离线模型支持`docling-tools models download`与`--artifacts-path`/`DOCLING_ARTIFACTS_PATH`。页级confidence用于发现风险，`table_score`在官方说明中仍未实现，不宜写成表格正确率。[本地RapidOCR例子](https://github.com/docling-project/docling/blob/main/docs/examples/rapidocr_with_custom_models.py)、[离线说明](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md)、[置信度范围](https://docling-project.github.io/docling/concepts/confidence_scores/)。

## 与 battle-scaling Skill 融合时应保留的边界

这些是本任务的证据管理建议：

- 条目引用必须含册名、PDF页码、可选印刷页码、块坐标或裁图、原文片段；正文改写与原文转写分列。
- 四册原定义、例外条件、适用范围与推导链保留在引用资源中；Skill主入口只写调用规则和索引，避免塞入未经核对的公式。
- 未验证公式、OCR不确定字、读序不明段落继续带状态传播；不能被摘要步骤抹平。
- 书中体系的名称/量级与其他战力体系映射需要单独论证，OCR工具只提供文本，不负责判断体系等价。
- 验收表至少包括总页数、OCR返回页、零文本复核页、语义阅读页、含公式页、公式已核对/待核对数，以及每个纠错项对应原图。

## 本次结论的实测边界

已验证的是官方当前版本、文档/API契约、公开文件大小、现装1.4.4源码与模型文件。未验证四册实际OCR准确率、完整运行耗时、CPU/内存峰值、每个公式工具对本书的增益。当前最有把握的行动是复用现装OCR做完整覆盖并建立可回看的证据，按难页/公式清单有针对性补缺。任何完整性声明都应依据逐页清单和视觉核对记录，而不是模型名或排行榜。

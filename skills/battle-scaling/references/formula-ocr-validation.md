# RapidLaTeXOCR 本册真实公式可用性实测

**结论：独立安装及CPU推理已跑通，但只能作为候选生成工具。** 3个原始公式裁图中，1个与原图符号结构一致、1个凭空多了星号、1个严重错识。同3个公式统一做一次阈值160去浅水印后，2个一致、1个仍严重错识。这是3例观察，不是全册准确率估计。

## 环境与调用

- 目录：`D:\Codex\tools\rapid-latex-ocr`；独立venv：`.venv`；`include-system-site-packages = false`。未执行全局pip安装或降级。
- 版本：RapidLaTeXOCR 0.0.9；Python 3.11；NumPy 1.26.4；ONNX Runtime 1.20.1；tokenizers 0.15.2；OpenCV 4.11.0.86；Pillow 10.4.0。依赖无torch；`pip check`通过。完整版本表保存在结果JSON。
- 官方接口为 `LaTeXOCR(image_resizer_path, encoder_path, decoder_path, tokenizer_json)(crop_path)`，返回`(latex, elapsed_seconds)`，没有公式置信度分数。[官方源码](https://github.com/RapidAI/RapidLaTeXOCR/blob/main/rapid_latex_ocr/main.py)
- 3个模型Session实测均只使用`CPUExecutionProvider`。测试脚本仅在内存中把官方SessionOptions约束为intra/inter线程各1及顺序执行，未修改已安装包；避免与主任务3个OCR worker争抢全部线程。
- 四文件取自[官方release v0.0.0](https://github.com/RapidAI/RapidLaTeXOCR/releases/tag/v0.0.0)，合计178,952,787字节，170.66MiB。官方资产未发布SHA-256；下列是本机下载后计算的复现hash，不假装为上游签名。

| 文件 | 字节 | 本地SHA-256 |
|---|---:|---|
| decoder.onnx | 50,952,726 | `bd695497bf1b22279b7626f5916c79226e1e244c84355f8da7edfd2d921d0072` |
| encoder.onnx | 89,008,136 | `01bf5dc25539ca0cd5b1bd29296ea495977a6ba5f629dc4178277809d26e5e7d` |
| image_resizer.onnx | 38,967,751 | `e0b075c39700f64d50400f39c8fc186bbb3b5d84d31864008313f376603aca9d` |
| tokenizer.json | 24,174 | `1dc27b18d6a518d0d5ff3f4bb7bd98521fe80ad39e5b2a246d4109f1bb9d5019` |

首次官方PyPI下载超时；GitHub连续下载被截短，长度校验及时拦截。第二条路径通过PyPI延长超时、固定兼容依赖，以及官方GitHub资产分段Range续传成功。无第三方镜像或替代权重。详情见`pip-install.log`、`pip-install-retry.log`、`installation.json`、`official-release-assets.json`和`model-manifest.json`。

## 输入与实际视觉比对

已先实际查看整页及裁图。均从本册原始嵌入页图直接裁切，无放大或重绘。坐标是原始页图像素上的`[left,top,right,bottom)`；PDF本地页、拼接序列页、印刷页脚和源图片hash均保存在`crop-manifest.json`。未选第20页跨行红色行内公式或第30页图示，以避免把不完整裁切当识别测试。

| 公式/位置 | 原图尺寸、裁图坐标 | 原始裁图输出耗时 | 原图比对 | 阈值160对照耗时/结果 |
|---|---|---:|---|---|
| I=(2/5)MR²；卷1本地21/序列21/页脚21 | [1152, 1628] / [190, 500, 430, 578] | 1.271s | 严重错识：原图 I=2/5 MR²，输出改成T、箭头、星号、Gamma、D、Omega等无关符号，丢失原式。 | 1.695s；去浅水印后仍生成无关书法T、箭头、星号、偏导符号等；并未恢复原式。 |
| T₂=T₁·(P₂/P₁)^((γ−1)/γ)；卷2本地50/序列150/页脚150 | [1152, 1628] / [255, 490, 885, 710] | 1.787s | 主结构、P下标和gamma指数一致，但等号上凭空增加 *；不能直接采用。 | 2.451s；去浅水印后不再多出星号；T/P下标、乘点、括号和(gamma-1)/gamma指数与原图一致。 |
| TKE=(1/2)ρHA∑fᵢvᵢ²；卷2本地100/序列200/页脚200 | [1220, 1726] / [210, 960, 1000, 1100] | 1.065s | 分数、rho、H/A、无上下界求和、f_i和v_i²与原图一致。空格与分组差异不改变所见式子。 | 1.176s；与未处理版本输出相同；符号及上下标结构与原图一致。 |

模型初始化耗时：原始组2.612s；阈值组1.931s。各组共享一个引擎，单页逐个运行；没有全书公式批跑。

阈值对照统一为灰度值<160置0，否则置255，再转RGB，无放大；同一规则应用于全部3例，没有按样本调参。原始裁图永久保留。此操作在本次3例中保留了可见符号，但不保证适用于灰色原文、细笔画或别的页面。

### 原始模型返回的LaTeX

- `inertia-p021`：

```latex
T\,\longrightarrow\,\stackrel{\longleftarrow}{\frac{\star}{\Gamma}}^{'*}\!\!\!\cdot\!\slash A^{\dagger}D\Omega^{2}
```

- `adiabatic-p150`：

```latex
T_{2}{=}^{*}T_{1}\cdot\left({\frac{P_{2}}{P_{1}}}\right)^{\frac{\gamma-1}{\gamma}}
```

- `tke-p200`：

```latex
T K E={\frac{1}{2}}\ \rho H A\sum f_{i}v_{i}^{2}
```

### 阈值160对照返回的LaTeX

- `inertia-p021`：

```latex
\bar{\cal T}\stackrel{\lbrack\star}{\longrightarrow}\stackrel{\iota\star}{\frac{\iota}{\partial\bar{\cal S}}}\bar{\cal S}\bar{\cal Q}^{\underline{{\alpha}}}
```

- `adiabatic-p150`：

```latex
T_{2}=T_{1}\cdot\left({\frac{P_{2}}{P_{1}}}\right)^{\frac{\gamma-1}{\gamma}}
```

- `tke-p200`：

```latex
T K E={\frac{1}{2}}\ \rho H A\sum f_{i}v_{i}^{2}
```

## 使用边界与复跑

本次实际比对是逐符号对照原图，没有安装LaTeX渲染器，未把输出重新渲染。符号转写一致仅证明该裁图的可见记号一致，不证明物理公式或书中论证正确。未测试本册幂塔/基数类公式，不能把本次物理公式结果外推到那些符号。

建议仅对需要识别的尚未校勘公式调用此候选工具，保留原图、候选LaTeX、视觉复核状态和错误说明。新候选中的未知符号、上下标、分数或幂塔须核原图；二值化改善不自动成为已验证。已有适用校勘、确定性工具或已验证模型时直接复用，不为日常评级重跑公式OCR或重复回看量级册。

复跑同3个原始裁图：

```powershell
& 'D:\Codex\tools\rapid-latex-ocr\.venv\Scripts\python.exe' 'D:\Codex\research\battle-scaling\handbook-20261018\formula-ocr-test\run_samples.py'
```

原始组数据：`formula-results.json`；阈值组数据：`formula-results-threshold160.json`；环境与源码hash：`environment-and-source.json`。复跑会覆盖该组JSON并恢复待视觉复核状态，勿将重跑结果当原先已核对的结果。

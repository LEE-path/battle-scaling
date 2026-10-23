# 原作读图、漫画与视频证据

本页是实际采用图像／视频证据时的读取规范。仅故事版按[文字取证边界](writing-rating-baseline.md#故事版取证边界)取消强制新读图／抽帧，不因引用共用定档流程而自动进入本页；独立评级与普通PK保持下述流程。无论哪种任务，声称自己看过画面仍须实际读取，不能以文本推断冒充视觉观察。

仅在有图片、漫画或视频时加载。`scripts/media.py` 提供本地信息、裁剪、测量、视频探测、带 PTS 的取帧和外部视觉请求协议。它**没有内置语义视觉模型**。Agent 必须实际调用可用的视觉能力读取原图，不能把这个工具的元数据结果称为已理解画面。

## 按需选择能力

```text
python scripts/media.py --input media-request.json --output media-result.json
```

API 为 `run(request: dict) -> dict`。`--input -` 可读 stdin。CLI 的 `--output` 是结果 JSON；请求内部的 `output` 是裁图、标注图或视频帧。路径必须是已有本地文件，不将 URL 交给 ffmpeg，也不会自动联网下载。

先运行：

```json
{"operation": "doctor"}
```

它检测 Python、Pillow、numpy、manga_ocr、tesseract、ffmpeg、ffprobe 是否存在；检测到不等于已经加载模型或完成 OCR。无 Pillow 时可以直接用 Agent 的图像读取／裁剪工具；无视频工具则用可访问的时间戳原帧。缺失必要视觉工具时应如实标注能力缺口，不让纯文本模型凭角色名臆造原图。

简单单页优先使用当前 Agent 的真实视觉入口。密集日文对白、字体困难或大量章节，可按需用现有 [manga-ocr](https://github.com/kha-white/manga-ocr)。MangaLMM/MangaVQA在本轮仅借鉴接口与语境组织，不调用其模型；不将九项外部项目模型加入后端。OCR 输出只作候选，必须与原图核对。

## 漫画读取流程

1. 绑定作品、版本、章节、原页码、扫描页码、语言、翻译版和来源。只使用可合法访问的原作、授权预览或用户提供素材；不可用时可继续用明确标注的转录／二手线索，不假称已见原图。
2. 阅读全页和前后页，再分析局部。确定阅读方向、跨页顺序、分镜边界；将回忆、梦境、假想、宣传图、搞笑画法和真实发生分开。
3. 逐格记录参与者、动作、对白和受击结果。对白需区分说话者、旁白、旁人猜测和权威设定；OCR 保留原文、译文及未辨识区。
4. 对战事件包含：谁攻击、哪招、状态、是否命中、命中位置、是否挡格／护盾／吸收／再生、后续伤势。血点、遮挡或页末切镜不能单独证明完全无伤或击杀。
5. 引用每项关键观察的页、格、边界框。量级推断另存，把“画面上看见什么”与“据此假设什么”分开。
6. 物体身份、材质、身高、尺寸未知时查资料并保留合理假设。漫画绘画比例和透视可能不一致，先评估是否可测再测。

单次输出/受击检查动作前、接触时和结果后的连续因果证据，并按 [feat-review.md](feat-review.md) 记录出力与状态。预损裂纹、他人同刻攻击、目标自爆、支撑失稳、内部储能等须区分贡献；皱眉、喘气、对白“认真了”或大特效可作线索，不能单独证明全力百分比、具体材料或全盛上限。

建议用结构化观察记录：

```json
{
  "id": "obs-page12-panel3",
  "source": "章节及可定位链接",
  "page": 12,
  "panel": 3,
  "image_sha256": "原图哈希",
  "bbox_xyxy": [50, 80, 400, 600],
  "visible_fact": "右侧人物的手部与横向木材接触；中间已有纵向裂纹",
  "interpretation": "可能沿纹劈裂，也可能有弯曲分量",
  "assumptions": ["人物身份由前页确认"],
  "unknowns": ["内部裂纹", "木材种类", "握力的方向和位移"],
  "inspector": "实际使用的视觉模型与工具记录"
}
```

## 按问题主动取证

借鉴ManGo的目标是少读无关格、保留每条线索的格号；其输入依赖已提供的分格框，不提供自动分格能力。由宿主实际看全页后列候选格框，或使用已经存在且经过核验的分格结果，再循环：

1. 写待判问题及当前缺口，例如“这次被击中的是身体还是护盾”“裂纹是否在发力前已有”。
2. 从已有页/格框中选能区分假设的下一格；保存 `question/selected_panel/selection_reason/pending_hypotheses`。
3. 用真实视觉读原格及必要前后页，保存 `source/page/panel/bbox/image_sha256/visible_fact/interpretation/unknowns`。框须落在图内，不能把负数、越界或空框当有效观测。
4. 写 `clue/supports/refutes/unresolved/next_check`，决定继续看相邻格、前后章、另一视角还是查文字/物性。已有证据不足时继续找，不因一次OCR成功就停止。
5. 结论已可区分、主要矛盾已处理或可用资料/预算耗尽才停止；保存 `stop_reason/checked_range/remaining_gaps`。预算耗尽不是“无此表现”，剪裁图未含上下文不是无反例。

参数提取后送 [推导账本](derivation-workflow.md) 绑定到真实公式。视觉回归采用有已知比例/PTS、可人工复查的小样本，保存真值来源、条件、误差与失败样本；不把QuantiPhy作者的旧预测当本机表现，也不把其尺寸误差直接换成角色档位。

## 图像信息与裁剪

```json
{"operation": "image-info", "path": "D:/evidence/page.jpg"}
```

输出文件哈希、保存尺寸、EXIF 方向与纠正后的宽高。所有后续坐标均按 **EXIF 校正后的完整图像**。这避免手机照片保存方向与屏幕方向错位。

```json
{"operation": "crop", "path": "D:/evidence/page.jpg", "box": [50, 80, 400, 600], "output": "D:/case/panel3.png"}
```

裁剪不拉伸、不补画，保留原件、源哈希、完整图坐标和 `source_offset`；裁图坐标加上 offset 才能映射回原图。默认拒绝覆盖已有输出，显式 `overwrite:true` 也不能覆盖输入证据原件。标注图和裁图属于分析辅助，不作为未经处理的原始图。

## 比例测量

```json
{
  "operation": "measure",
  "path": "D:/evidence/frame.png",
  "reference_segment": [[100, 50], [300, 50]],
  "target_segment": [[100, 150], [250, 150]],
  "reference_length_m": 2.0,
  "reference_source": "原作明确给定／已校准物体，来源和定位",
  "same_plane": true,
  "equal_projected_scale": true,
  "pixel_error": 2,
  "reference_length_error_m": 0.05,
  "output": "D:/case/measured.png"
}
```


(L_t=(p_t/p_r)L_r)。两个布尔前提需要由画面研究证实；**同一平面不自动保证透视投影的局部比例相等**。远近不同、朝向不同、人体屈曲、镜头畸变或漫画比例失真时，先做有足够控制点的相机标定／平面单应校正，或分别估计几何情景；不能用立绘身高直接缩放远处物体。

`pixel_error` 表示每个端点位置的欧氏误差上界，脚本保守地给线段长度 ±2 倍该值；再与已知参照长度误差组合得到区间。这不包含未知景深和模型错误。输出含原始坐标、公式、比例、区间、假设、源哈希及可选标注图；标注图维持完整原图几何。

只测长度，不识别物体、不鉴定木种、不推导角色身高、动作或力量。力臂和握持点需要额外受力图。面积、体积需另证几何形状和第三维，不能从一条长度直接假设立方体。

## 视频：先探测，再按实际 PTS 取帧

```json
{"operation": "video-probe", "path": "D:/evidence/clip.mkv", "timeout_seconds": 30}
```

输出所选普通视频流、起始时间、时基、帧率、时长和流侧数据。封面图片不作为视频流。`avg_frame_rate` 仅是描述值，变帧率不能用“第几帧÷平均帧率”替代实际时间戳。

```json
{"operation": "video-extract", "path": "D:/evidence/clip.mkv", "timestamp_seconds": 0.21, "output": "D:/case/frame.png"}
```

`timestamp_seconds` 是相对所选视频流起点的播放时间。工具用 accurate seek、`-copyts` 与 `showinfo` 保存原始 PTS，返回首个可解码且不早于请求时间的帧、`actual_source_pts_seconds`、相对流起点的 `actual_playback_seconds`、帧哈希。5 fps 的视频请求 0.21 秒会得到 0.4 秒原帧；不会创造“0.21 秒画面”。工具不会把 PTS 换称剧情时间。

所有子进程使用参数数组、无 shell；本地协议限制为 file／pipe，操作有 1～60 秒超时。取帧输出先写临时文件再替换目标，失败不会伪留成片。大视频或异常时间轴需要缩小片段，保留切片的绝对起点映射。

动作测量至少读取起点、接触点、结束点及其前后帧。明确快慢动作、镜头跳切、重复播放、镜头运动、遮挡、帧混合和角色自身位移。普通影视的播放耗时不是自动可信的世界内时长；若只能估计，报告速度情景及其前提。漫画分镜之间无明示时长时，不能把页数当帧数。

## 外部视觉请求协议

```json
{"operation": "vision-request", "path": "D:/evidence/page.png", "task": "按阅读顺序列出人物、动作、台词归属和破防证据；给出框坐标及未辨识区"}
```

输出 `status:requires_external_vision` 和统一响应结构，**不会执行视觉推理**。支持视觉的 Agent 应通过自身图像入口实际读图，并填写 inspector、observations、interpretations、unreadable_regions、missing_context；外部适配器亦遵守同一协议。没有真正看到原图的模型不得填写观察记录。

## 官方工具依据与适配原则

- [Pillow 文档](https://pillow.readthedocs.io/en/stable/)：解码、EXIF 校正、无缩放裁剪及分析标注。
- [ffprobe 文档](https://ffmpeg.org/ffprobe.html)、[ffmpeg seeking / copyts](https://ffmpeg.org/ffmpeg.html)、[showinfo](https://ffmpeg.org/ffmpeg-filters.html#showinfo)：流信息与真实时间戳。
- [OpenCV homography 教程](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html)：平面投影关系；工具并未因引用该页而自动完成标定。
- OCR／漫画模型只按需安装、调用；无需为简单图片启动完整模型。对模型的叙事猜测、OCR 幻读和视觉误识别，必须通过原图、上下文和独立观察复核。

本工具不提供“把任何图像自动变成正确战力结论”的承诺。它提供可审计的读图入口、测量和取证步骤，让有真实视觉能力的 Agent 按证据完成研究。

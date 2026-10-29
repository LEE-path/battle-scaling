# Complete capability map / 完整能力与安装入口

完整发行包提供原创可分发代码、规则、方法、透明模板、字体及安装流程。它不包含其他Agent的模型、私人账号、API Key、完整原作、参考歌曲、角色素材或第三方模型权重。**随包代码、依赖已安装、账号已授权、模型可生成，是不同状态。**默认推荐下载完整包；Skill-only包不包含`tools/`下的安装器、独立拆书工具和视频工程。

The full ZIP includes the portable implementation and setup paths. Host reasoning/search/vision and external accounts or generators must be supplied by the user. Do not interpret a shipped adapter as an already connected service.

| 能力 / Capability | 随包入口 / Shipped entry | 安装或使用条件 / Setup |
|---|---|---|
| 汪吧/VSB综合评级与九维 | `skills/battle-scaling/SKILL.md`, `scripts/battle.py`, rulesets/data/references | `core`或`full`；原作研究与语义裁决由宿主实际执行 |
| 物理、数学与叠链 | physics/high/derivation等脚本与具名已校勘规则 | 核心计算用标准库；`research`提供SymPy/Pint。公式正确不认证证据归属 |
| 首次小说建档及补章 | `scripts/novel_refpack.py`, `scripts/combat_refpack/`, `tools/combat-novel-refpack/` | 标准库核心；用户提供可读取原文，Agent实际读书与取证 |
| 论文、官方设定与跨角色搜证 | research/evidence/discovery流程、站点导航与检索方法 | 宿主搜索/联网工具；按当前权限访问。API服务或其他Skill不是内置账号 |
| 贴吧搜索、帖子、楼层与图片链接 | `scripts/tieba.py`, `scripts/tieba_aiotieba.py` | `research/full`安装aiotieba；匿名只读适配，访问结果受网络与站点限制 |
| 战斗分析、过程与故事 | matchups/process/writing入口及可复用写作经验 | 独立评级先行；宿主写作。用户作品全文不是运行依赖 |
| 网页原图/媒体链接发现与下载 | `scripts/media_acquire.py`, `assets/media/source-catalog.json` | `inspect/download/probe/clip/frame`；Pillow和FFmpeg按需，浏览器动态资源由宿主提供 |
| 多平台视频与图库 | yt-dlp/gallery-dl安装配方、检索词和来源/选材流程 | `media/full`；支持站点、登录与下载权限按真实状态；不复制第三方虚拟环境 |
| B站搜索、扫码登录、分P与高清流 | `scripts/bili_media.py` | `media/full`；用户扫码，自己的画质权限；不依赖JiJiDown程序或私有解析服务 |
| 原图/视频核验、截帧与测量 | `scripts/media.py`, `scripts/media_acquire.py`, `scripts/vision_adapter.py` | Pillow、FFmpeg；视觉API适配器需用户端点、模型及密钥环境变量，亦可用宿主读图 |
| 扫描PDF OCR | `scripts/ocr_pdf.py` | 显式`setup.py optional ocr`；兼容旧RapidOCR接口，OCR结果仍需核对 |
| 公式识别 | `scripts/formula_adapter.py` | 显式`optional formula`，已有四个本地模型文件；或宿主人工视觉转录 |
| PK海报 | `scripts/poster.py`, `assets/media/pk-cover/` | `media/full`；默认姓名/版本/VS/分界/品牌，无评级栏；用户提供人物图 |
| 一图流 | `scripts/one_image.py`与选图/贴脸流程 | `media/full`；用户提供可用水龙表情图和人物图；不附漫画原图 |
| 卡点视频与可编辑工程 | `tools/battle-video-studio/`, V01—V09、透明VS、品牌、字体 | `media/full`并安装Node/npm、FFmpeg、Chrome/Edge；用户导入与所选时序一致的音轨及人物素材 |
| 最终视频审片 | `tools/battle-video-studio/scripts/review-video.mjs` | FFmpeg；从真实成片展开短槽位全部帧与接点，宿主实际看，不自动判断脸部或精彩 |
| 参考视频复刻 | `references/video-template-replication.md`及可编辑Studio | 用户参考音视频，宿主能观察；拆结构、卡点、动效、入场与片尾，再实现新模板 |
| 生图/生视频、CLI/MCP/API及本地模型 | `references/media-integrations.md`, `scarce-character-media.md` | 绑定用户已有平台/工具，按真实接口测试输出；图像和视频可用不同后端。下载本地模型前说明配置与空间，由用户选择 |
| 站点与素材经验积累 | site_registry/source-catalog与积累流程 | 默认方法随包；使用者运行库自己建立，升级保留，不附他人的私人访问记录 |

## Quick routes / 快速入口

在完整包根目录：

```sh
python -X utf8 tools/setup.py install --profile full --skill-dir your-agent-skills/battle-scaling
python -X utf8 tools/setup.py check
python -X utf8 tools/setup.py run battle doctor
python -X utf8 tools/setup.py run media_acquire --help
python -X utf8 tools/setup.py run bili_media --help
python -X utf8 tools/setup.py run poster --help
python -X utf8 tools/setup.py run one_image --help
python -X utf8 tools/setup.py run video_studio select-template
```

For optional OCR, see [INSTALL](INSTALL.md). For generation backends, the Agent uses the actual host tools or follows the shipped API/MCP/CLI/local-model integration workflow. No universal generator, paid quota or H3 runtime is implied by installation. Heavy models are not part of the full ZIP.

素材能下载不等于适合成片或有权再分发；最终仍按媒体用途与审片规范选择。发布准备检查与普通评级/媒体制作分开，使用者无需每次出图重跑全项目测试。

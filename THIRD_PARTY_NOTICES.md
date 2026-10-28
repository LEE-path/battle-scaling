# 第三方来源、许可证与鸣谢 / Third-party notices and acknowledgements

核查更新 / Updated: **2026-10-27**。新增视频依赖与 SCP 题集署名；原有来源各自保留实际核查日期。范围是当前发布包，不包括仓库提交历史。 / New video dependencies and SCP benchmark attribution were reviewed; existing sources retain their recorded review dates. Scope: the current distribution, not repository history.

## 许可边界 / License boundaries

本仓库根目录的 MIT 许可证适用于项目原创软件及明确纳入该许可的原创文档，**不重新授权第三方资料、上游代码、作品角色、漫画、小说、影视画面、社区规则说明或模型**。本文件列出的例外和各文件原有声明优先适用。公开可访问、添加鸣谢和软件可运行，均不等于已取得其他权利人的全部授权。

The root MIT license covers this project's original software and original documentation expressly placed under it. **It does not relicense third-party material, upstream software, fictional characters, comics, novels, film images, community rule explanations or models.** The exceptions below and existing file-specific notices remain applicable. Public access, acknowledgement and successful execution are not substitutes for the applicable permissions.

发布包不附带九个研究项目的源码、模型、权重、训练集、社区全库，也不包含完整量级册 PDF/OCR 或整部原作。可选工具由使用者按需安装；本说明没有把“研究过”写成“运行依赖”。这是一份发布包来源与许可核查，不是权利人授权或法律无争议证明。

The package does not bundle the nine research projects' code, models, weights, training sets or complete community datasets, nor full handbook PDFs/OCR or complete original works. Optional tools are installed separately when needed. Research references are distinguished from runtime dependencies. This is a package provenance and licensing review, not a grant of rights or a guarantee that no dispute can arise.

## 1. 拆书流程来源 / Novel-refpack provenance

感谢 **[scp3500/novel-refpack](https://github.com/scp3500/novel-refpack)**。它提供了单书隔离、结构抽取、分片任务和逐层汇总的参考。论战版重新组织为原文定位、逐段表现、关系证据、状态继承与宿主验收流程，不运行原工程，也不打包其书包、配置或模型。

We thank **[scp3500/novel-refpack](https://github.com/scp3500/novel-refpack)** for the single-book isolation, structural extraction, chunk tasks and hierarchical aggregation design. The combat edition reorganizes the workflow around source locations, feats, relations, state inheritance and host review. It does not run the original project or bundle its book packs, configuration or models.

- 上游许可 / Upstream license: [MIT](https://github.com/scp3500/novel-refpack/blob/main/LICENSE), copyright **2026 novel-refpack contributors**.
- 通知副本 / Preserved notices: [`tools/combat-novel-refpack/LICENSE.upstream-novel-refpack`](tools/combat-novel-refpack/LICENSE.upstream-novel-refpack) and [`skills/battle-scaling/assets/licenses/novel-refpack-MIT.txt`](skills/battle-scaling/assets/licenses/novel-refpack-MIT.txt).
- 真实仓库已通过许可证及多个文件的字节指纹与原本地来源匹配；没有为旧下载虚构提交号。 / The repository was matched to the original local source through the license and multiple exact file fingerprints. No commit ID has been invented for the historical download.
- 具体来源及改造边界 / Details: [`tools/combat-novel-refpack/UPSTREAM.md`](tools/combat-novel-refpack/UPSTREAM.md).

## 2. 按需运行的工具 / Optional runtime tools

这些是代码会按功能调用或作为回退读取器使用的独立工具，**未随包分发其实现或二进制**。主源许可按本次核查填写；实际安装版本、二进制构建、依赖与模型资产还须遵守随附条款。Python 标准库、宿主 Agent 的搜索及视觉能力不属于以下九个研究项目提供的模型。

These independently installed tools are invoked for specific functions or fallback reading. **Their implementations and binaries are not redistributed in this package.** The table records the primary-source licenses reviewed for this release; the installed version, binary build, transitive dependencies and model assets retain their own terms. Python's standard library and the host Agent's search/vision are not models supplied by the nine research projects.

| 工具 / Tool | 使用点 / Use | 主源与许可 / Primary source and license |
|---|---|---|
| [Pillow](https://github.com/python-pillow/Pillow) | 图像读取和预处理 / Image reading and preprocessing | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| [NumPy](https://github.com/numpy/numpy) | OCR 图像数组 / OCR image arrays | [BSD-3-Clause](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | 可选公式 OCR 推理 / Optional formula OCR inference | [MIT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) |
| [RapidLaTeXOCR](https://github.com/RapidAI/RapidLaTeXOCR) | 显式启用的本地公式 OCR / Explicitly enabled local formula OCR | [MIT](https://github.com/RapidAI/RapidLaTeXOCR/blob/main/LICENSE)；模型文件另核 / Verify model assets separately |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) (`rapidocr_onnxruntime`) | 可选 PDF OCR / Optional PDF OCR | [Apache-2.0](https://github.com/RapidAI/RapidOCR/blob/main/LICENSE)；模型及依赖另核 / Verify models and dependencies separately |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | 可选 PDF 阅读、渲染和 OCR 页面准备 / Optional PDF reading, rendering and OCR preparation | [AGPL-3.0](https://github.com/pymupdf/PyMuPDF/blob/main/COPYING) 或适用的商业许可 / or an applicable commercial license; see the explanation below |
| [pypdf](https://github.com/py-pdf/pypdf), [PyPDF2](https://github.com/py-pdf/PyPDF2) | 已安装时使用的 PDF 文字读取回退 / Installed PDF text-reading fallbacks | [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE), [PyPDF2 license](https://github.com/py-pdf/PyPDF2/blob/main/LICENSE) |
| [jieba](https://github.com/fxsjy/jieba) | 可选中文分词 / Optional Chinese segmentation | [MIT](https://github.com/fxsjy/jieba/blob/master/LICENSE) |
| [aiotieba](https://github.com/lumina37/aiotieba) | 独立 worker 的贴吧公开资料读取 / Public Tieba reading in a separate worker | [Unlicense](https://github.com/lumina37/aiotieba/blob/master/LICENSE) |
| [FFmpeg / ffprobe](https://github.com/FFmpeg/FFmpeg) | 可选视频元数据与抽帧 / Optional video metadata and frame extraction | [通常 LGPL-2.1-or-later；启用 GPL 组件等会改变条件](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md) / Usually LGPL-2.1-or-later; GPL components and build options can change the applicable terms |

**PyMuPDF / MuPDF：**本项目不打包这两个库，也不以 MIT 声明覆盖其 AGPL。单独安装不自动消除组合、修改、分发或网络服务场景中的许可义务。启用相关路径前，应按实际使用方式遵守 AGPL，或取得 Artifex 的适用商业许可；涉及组合程序是否需要提供对应源码，应依据真实组合方式与许可条款判断，不能仅靠“可选依赖”或鸣谢认定合规。[官方许可说明](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) / This project does not bundle PyMuPDF/MuPDF or place them under MIT. Separate installation does not automatically remove obligations arising from combination, modification, distribution or network use. Follow the applicable AGPL requirements or obtain an appropriate Artifex commercial license. Obligations for a combined program depend on the actual integration and license terms; optional status or acknowledgement alone is not a compliance determination.

仅作阅读工具建议、未进入默认代码调用链的 [manga-ocr](https://github.com/kha-white/manga-ocr) 等工具，仍须按各自仓库核对许可。 / Tools mentioned as recommendations, such as [manga-ocr](https://github.com/kha-white/manga-ocr), are not part of the default call chain; consult their repositories before use.

## 3. 研究与流程鸣谢 / Research and workflow acknowledgements

以下主要是目标、流程和接口层面的参考。当前包不导入这些项目的软件包，不启动其服务，不调用其专用 API，也不附带它们的模型、源码或数据。**“借鉴”不表示整套实现已经复现。**

The following informed goals, workflows or interfaces. The package does not import their software packages, start their services, call their dedicated APIs, or bundle their models, source code or datasets. **Inspiration does not mean that the complete upstream implementation has been reproduced.**

| 来源 / Source | 参考内容 / Influence | 已核许可与边界 / License status and scope |
|---|---|---|
| [AutoSkill: fictional_battle_simulation](https://github.com/ECNU-ICALK/AutoSkill/blob/main/SkillBank/ConvSkill/english_gpt3.5_8_GLM4.7/fictional_battle_simulation/SKILL.md) | 由已给属性组织战况 / Narrating a battle from provided attributes | README 有 MIT 徽章，但未找到完整根许可证；不分发上游 Skill 原文 / README displays MIT, but a complete root license was not found; upstream Skill text is not redistributed |
| [OmniBattle AI](https://github.com/Zerhal/omnibattle-ai) | 分阶段检索与角色关系 / Staged retrieval and character relations | [MIT](https://github.com/Zerhal/omnibattle-ai/blob/main/LICENSE), 2025 OmniBattle AI Contributors |
| [VS Simulator / vskill](https://github.com/GentleClash/vskill) | 意图、裁决、状态与叙事分离 / Separating intent, adjudication, state and narration | 未找到明确许可证；仅流程参考 / No explicit license found; workflow reference only |
| [Fictional Character Ranking](https://github.com/BenCantCode/fictional-ranking) | 对战与资料版本可追溯 / Traceable matchup and source versions | 未找到明确许可证；仅方法参考 / No explicit license found; methodology reference only |
| [Animal Battle Stats](https://github.com/RamiNoodle733/animal-battle-stats) | 物种字段、论文发现和实测／估计区分 / Species fields, literature discovery and measured/estimated values | [MIT](https://github.com/RamiNoodle733/animal-battle-stats/blob/main/LICENSE), 2025 Animal Battle Stats Team |
| [Cited Feats](https://citedfeats.com/data/) | 作品、连续性、事件与引文定位 / Work, continuity, event and citation indexing | 网站／可选数据来源，非程序依赖；许可例外见下一节 / Website and optional data source, not a software dependency; see the next section |
| [QuantiPhy](https://github.com/Paulineli/QuantiPhy) | 已知先验下的测量与误差检验 / Measurement with known priors and error checking | [MIT](https://github.com/Paulineli/QuantiPhy/blob/main/LICENSE), 2025 Puyin Li |
| [MangaLMM / MangaVQA](https://github.com/manga109/MangaLMM) | 漫画文字、框与上下文接口 / Manga text, boxes and contextual interfaces | [代码 MIT](https://github.com/manga109/MangaLMM/blob/main/LICENSE), 2025 manga109 team；[Manga109 数据另有禁止再分发条款](https://www.manga109.org/en/download_s.html)，代码许可不覆盖漫画 / Code license does not cover manga; Manga109 has separate non-redistribution terms |
| [ManGo paper](https://arxiv.org/abs/2608.29865) | 面向问题主动选格、保留线索与停止判断 / Question-directed panel selection, grounded clues and stopping | 论文 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；本次未找到作者实现仓库，不用同名无关仓库替代 / Paper licensed CC BY 4.0; no author implementation repository was located, and unrelated same-name repositories are not substituted |

## 4. 可选社区数据 / Optional community data

**Cited Feats：**导入仅处理用户显式提供的本地文件；不在发布包中预置社区全库。一般数据按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 署名、链接和注明改动。官网明确 **SCP Foundation 行（`scp`）改用 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)**，不能统一改写成 CC BY 4.0。混合文件保留逐记录许可、原来源与作者信息；缺失的作者或权利信息不得编造。重分发或改编这些 SCP 数据时须遵守对应署名及相同方式共享要求。数据许可不自动覆盖原作漫画、小说、图像或站点程序。

**Cited Feats:** import is limited to local files explicitly supplied by the user; no complete community dataset is bundled. General data is attributed and linked under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with changes identified. The official site explicitly places **SCP Foundation rows (`scp`) under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)** instead. Mixed files retain record-level licenses, original sources and author information; missing rights information must not be invented. Redistribution or adaptation of those SCP rows must meet the corresponding attribution and ShareAlike requirements. A data license does not automatically cover the original comics, novels, images or website software.

署名示例 / Attribution example: **Data: Cited Feats (https://citedfeats.com/data/), CC BY 4.0 except SCP rows under CC BY-SA 3.0. Changes: converted to research leads, preserving original citations.** 若只使用其中一种许可的数据，应按实际子集调整。 / Adjust the statement to the actual subset used.

## 5. VSB 模式：改编资料的许可例外 / VSB mode: adapted reference material

感谢 **[VS Battles Wiki contributors](https://vsbattles.fandom.com/wiki/VS_Battles_Wiki)**。本包 VSB 模式对其档位、属性、计算及对战规则作中文整理、结构化和执行适配，保留原页与已核修订链接。它是独立实现，**不代表 VS Battles Wiki 官方产品、认可或合作**。

We thank **[VS Battles Wiki contributors](https://vsbattles.fandom.com/wiki/VS_Battles_Wiki)**. This package translates, summarizes and structures its tiering, attribute, calculation and matchup rules for an independently implemented VSB mode. Source pages and reviewed revisions remain linked. **This is not an official, endorsed or partnered VS Battles Wiki product.**

官方 [版权页](https://vsbattles.fandom.com/wiki/VS_Battles_Wiki:Copyrights) 及 Fandom [许可帮助](https://community.fandom.com/wiki/Help:Licensing) 的当前公开 API 正文均声明默认文本为 **[CC BY-SA 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/)**，另有说明的内容除外。当前网页直接访问受阻，许可证结论来自真实成功的官方 MediaWiki API，不把搜索摘要称为已读网页。回执见 [`UPSTREAM-SOURCES.json`](UPSTREAM-SOURCES.json)。

The current text returned by the official MediaWiki APIs for the [copyright page](https://vsbattles.fandom.com/wiki/VS_Battles_Wiki:Copyrights) and Fandom's [licensing help](https://community.fandom.com/wiki/Help:Licensing) specifies **[CC BY-SA 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/)** for default text, unless otherwise stated. Direct webpage access was blocked; this finding comes from successful official API responses, not from presenting a search snippet as a read page. See [`UPSTREAM-SOURCES.json`](UPSTREAM-SOURCES.json).

**本发布包的明确例外 / Explicit release exceptions:**

- `skills/battle-scaling/references/vsb-*.md` 中对 VSB 规则的翻译、改编和说明，以及 `skills/battle-scaling/rulesets/vsb-current-*.json` 中结构化的 VSB 资料，按 **CC BY-SA 3.0** 提供，署名 VS Battles Wiki contributors；本项目负责翻译、摘要、格式转换及适配修改。对应原始页和修订链接在这些文件中。 / Translated/adapted VSB rule explanations in `references/vsb-*.md` and structured VSB reference material in `rulesets/vsb-current-*.json` are offered under **CC BY-SA 3.0**, attributed to VS Battles Wiki contributors. Project changes include translation, summarization, format conversion and adaptation. Original page and revision links are retained in those files.
- 独立编写的通用程序代码按根 MIT 许可；这不把上述 VSB 改编资料改成 MIT，也不意味着所有独立输出自动采用同一种许可。复用 VSB 改编说明时仍需保留署名、来源链接、改动说明和 ShareAlike。 / Independently written program code uses the root MIT license. This does not turn adapted VSB references into MIT material or automatically assign a single license to every independent output. Reuse of adapted VSB explanations retains attribution, source links, modification notices and ShareAlike requirements.
- VSB 上引用的第三方角色、截图与媒体不因 Wiki 文本许可而获得统一授权；本发布包不分发它们。 / Third-party characters, screenshots and media referenced by the wiki are not automatically licensed by its text license and are not redistributed here.

## 6. 其他原作、规则与服务 / Other works, rules and services

汪吧标准、评定组讨论及其他社区资料的名称和来源链接用于口径说明与搜证。未找到明确授权时，不宣称原册或帖子已由 MIT 授权；原册作者、发帖者和原作权利人的权利仍各自保留。本包不分发完整原册、整书、漫画页或影视截图。对事实、数学关系及程序自主说明的使用，不等于获得对原有受保护表达和编排的无限再分发权。

Wangba standards, assessment discussions and other community sources are named and linked for standards identification and research. Without an explicit grant, the original handbook or posts are not represented as MIT-licensed; their authors and original-work rights holders retain their respective rights. Full handbooks, books, comic pages and film screenshots are not bundled. Use of facts, mathematical relations and independently written explanations does not grant unlimited redistribution rights over protected source wording or arrangement.

Europe PMC、百度贴吧、GitHub、arXiv、OpenAI 兼容服务等是按需资料／协议来源，不是被本仓库再许可的内容或模型。实际访问、素材上传和输出再分发还须服从对应服务条款与素材许可。 / Europe PMC, Baidu Tieba, GitHub, arXiv and OpenAI-compatible services are optional research or protocol sources, not content or models relicensed by this repository. Their service terms and the source material's license continue to apply to actual access, uploads and redistribution.

## 7. 视频工程 / Video project

| Component | Use and license |
|---|---|
| [Remotion](https://github.com/remotion-dev/remotion), pinned 4.0.539 packages | Preview, layout, effects, bundling and export. **Remotion License**, not MIT; the installed `LICENSE.md` and upstream main license were checked on 2026-10-27. Individual, eligible small-organization/nonprofit/evaluation uses and Company License requirements follow the actual license. See [upstream terms](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) and `tools/battle-video-studio/licenses/Remotion-LICENSE.md`. Dependency source/binaries are installed with npm, not bundled. |
| [Smiley Sans / 得意黑](https://github.com/atelier-anchor/smiley-sans) 2.0.1 | Bundled unchanged `SmileySans-Oblique.ttf`; copyright atelierAnchor, 2022–2024. **SIL Open Font License 1.1**, reserved names Smiley/得意黑. Font and complete notice stay together under `public/fonts/`; not relicensed as MIT. |
| React / React DOM | MIT dependencies, separately installed by npm. |
| TypeScript | Apache-2.0 development dependency, separately installed by npm. |
| FFmpeg / ffprobe; Chrome / Edge | External media/browser tools. Their own build and distribution terms apply; executables are not bundled. |

Project code and original reusable VS/branding graphics retain their included MIT license. The timing presets preserve observed cut timing and independently implemented presentation parameters; they do not include a song, source video, character image or a right to redistribute such media. Users obtain permitted media themselves, import a matching audio edit with `scripts/import-music.mjs`, and provide character assets via the workbench or job paths. A timing match, download success or third-party acknowledgement does not grant media rights.

## 8. SCP 语义题集 / SCP-derived semantic benchmark portions

`skills/battle-scaling/benchmarks/semantic-boundaries/` includes short textual selections, Chinese contextual paraphrases and adapted questions/review criteria from:

- **SCP-3143 — Murphy Law in… The Foundation Always Rings Twice!**, by [The Great Hippo](https://www.wikidot.com/user:info/the-great-hippo), [original article](https://scp-wiki.wikidot.com/scp-3143).
- **SCP-3812 — A Voice Behind Me**, by [djkaktus](https://scp-wiki.wikidot.com/djkaktus), [original article](https://scp-wiki.wikidot.com/scp-3812).

These SCP-derived portions and their adaptations use **[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)**. Changes include short selection, Chinese paraphrase, contextual summary, adversarial reasoning examples and review criteria. Keep author/source/license links and applicable ShareAlike terms when reusing them; the root MIT license does not override these portions. Original generic recorder code remains independently MIT-licensed. Non-SCP source excerpts retain their own rights; no complete screenplay, novel, source article, SCP story or image is bundled. See the [SCP Licensing Guide](https://scp-wiki.wikidot.com/licensing-guide).

## Optional DEATH BATTLE! cover variant

`skills/battle-scaling/assets/media/pk-cover/variants/cosmic-death-battle/template-1920x1080.png` is an optional generated layout example bearing the **DEATH BATTLE!** wording. Its generation instructions are preserved in the adjacent `template-prompt.txt`; it was generated with that text, rather than supplied as an official brand asset. The underlying show/brand is [DEATH BATTLE](https://deathbattle.gg/en-usd). The brand wording and any associated trademark rights are **not** represented as project-owned or granted under MIT. This package has no affiliation, sponsorship or endorsement from DEATH BATTLE. No license to a third-party brand is granted by this example. The default original cover designs and the video's silver VS remain available independently.


## Media and research installation profiles

The full installer downloads these dependencies into the user's isolated environment; their source/binaries are not vendored into this distribution. Versions are recorded in `tools/requirements/constraints-tested.txt`. Declared licenses were checked from the successfully installed package metadata on 2026-10-28.

| Dependency | Use | Declared license / upstream |
|---|---|---|
| [requests](https://github.com/psf/requests) | HTTP and platform requests | Apache-2.0 |
| [python-qrcode](https://github.com/lincolnloop/python-qrcode) | User-confirmed QR login | BSD; its dependencies retain their own terms |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Video format resolution and downloads | Unlicense; optional bundled or linked components have separate terms |
| [gallery-dl](https://github.com/mikf/gallery-dl), [upstream](https://codeberg.org/mikf/gallery-dl) | Image galleries and supported media sites | GPL-2.0-only |
| [bilibili-api-python](https://github.com/Nemo2011/bilibili-api) | Optional direct Bilibili clip resolver in `media_acquire.py` | GPL-3.0-or-later |
| [SymPy](https://github.com/sympy/sympy) | Optional symbolic mathematics | BSD |
| [Pint](https://github.com/hgrecco/pint) | Optional physical units | BSD |

GPL dependencies are not relicensed as MIT. If redistributing them or a combined program, evaluate and meet the applicable GPL terms; installing them separately or describing them as optional is not a blanket license exemption. The root MIT license covers original project portions only.

The unchanged Smiley Sans font and its OFL notice are also supplied in `skills/battle-scaling/assets/media/fonts/` for portable collage output, in addition to the video project's `public/fonts/`. Keep each font with its notice.


## Linked showcase media

The README and Release page separately embed existing edited character-media examples and display copies. These are presentation examples, not an MIT-licensed stock-media library or a source of canonical rating evidence. Their film, animation, character art, manga sticker and music rights remain distinct from the original project code, templates and brand graphics. The installable archives do not preload that footage or audio. Source-level credits and the scope of SCP-derived material are listed in [showcase notes](docs/SHOWCASE.md).

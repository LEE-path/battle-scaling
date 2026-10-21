[简体中文](README.md) | [English](README.en.md)

# battle-scaling

**论战评级、原作取证与 VS 推演 Agent Skill · 1.7.4**

把“这个角色有多强、凭什么、对上另一方怎么赢”整理成可追溯的证据和结论。当前宿主 Agent 负责搜索、阅读、读图与语义判断，Python 工具负责定位、计算、约束检查和归档；无需下载其他项目的模型。

## 主要能力

- **角色评级**：固定作品、连续性、版本、时期、状态和装备，分别评定输出、体防、智力、战斗智商、经验、特殊技能、破坏、速度、体量。
- **搜证与反证**：查原作、官方资料和社区线索，记录章节、页码、时间戳、原句或画面位置；同时追查失败、限制、状态变化和相反表现。
- **单次表现审查**：区分实际做到、合理估计、已证全力或上限；核对因果、材料、疲劳、伤势、战意、装备与外援，不把一次毁伤自动当作全盛上限。
- **物理计算与关系叠加**：保存公式、参数来源、单位、假设和中间值，检查跨角色、跨状态的继承条件、倍率及循环论证。
- **高层结构与特能**：按具名规则审查无限、数学结构、叙事层次及论外等主张；另查特殊能力的影响上限、发动、对象、抗性与反制。
- **单挑与多人 VS**：分析双方可行胜路、反制与翻盘条件；按需输出带证据和状态变化的完整假想战况。
- **小说建档**：从 TXT、MD、EPUB、DOCX 建快照和倒序阅读任务，保留逐字引句、正反表现、状态线、交锋、九维缺口及候选 CASE。

索引、哈希和测试通过不代表自动读懂原作，也不认证任意角色评级。跨作品兼容、模型适用性与最终裁决仍需宿主 Agent 审查。

## 默认评级与三种口径

未指定时使用**常态**。回答先给“角色（版本）量级：具体常态主档”，再列**常态九维卡**，每项包含主判、原作出处和叠法；最高与扒下限放在后续分析。用户明确指定其他模式或三模式并列时按指定执行。

| 口径 | 取证方式 |
|---|---|
| 常态 `normal` | 表现优先于冲突设定；同版本、同状态下，取多数可信表现中的最高，优先有重复支持的表现群。样本不足时标为暂定。 |
| 最高 `highest` | 允许极端或孤例表现、最强或同级声明及形容词强解释参与推导，逐项展示扩张与假设。 |
| 扒下限 `lowball` | 主动追查虚弱、受伤、破防、异常低输出、下位击败等，保留当时状态与前提，给最低可论证分支。 |

三种口径独立取证和推导，不混用互斥峰值配置。总档不自动覆盖体防或速度；智力、战斗智商、经验等按表现给能力等级，不编造“爆楼智力”之类档名。

## 搜证与证据等级

优先原始语言原作与官方资料，区分事件、旁白、角色台词、作者补充、社区解释和研究假设。搜索摘要只是入口；未核的二手纯文字表现转述，在找到原作证据前不参与任何模式定级。

允许网络搜证时，社区入口先查汪峰在吧的角色总集及相关帖子；资料不足时补查抖音论战吧，同时推进原作核查。

| 材料 | 默认可信度与用途 |
|---|---|
| 两吧身份与结论归属已核的评定组评级、叠法 | **中**：作为外部评级参考、推导候选和查证路线；具体表现仍需原作支持。 |
| 普通量级讨论、个人推测、身份未核的“评定组”帖子 | **低**：作为线索，不能只凭档名或重复转述定级。 |
| 已实际读图，并核对原作、版本、状态和前后语境的原图 | **高**：支持图中事件或声明；不自动认证整帖观点、计算或档位。 |
| 没有原作依据的纯文字表现转述 | **未证实，仅线索**：不作定级锚点或关系叠边。 |

已核的小说正文、官方文字与校勘转录可直接构成原作证据，不要求必须有截图。可信度不是胜率；网页取得成功也不等于正文已读或事实已核。

可选[贴吧读取工具](skills/battle-scaling/references/tieba-reading.md)支持匿名搜索、正文分页、楼中楼、图片地址、快照、哈希和断点续抓，按需使用独立 `aiotieba` 环境。图片链接不等于已读图，抓全当前可见页也不等于恢复了删帖或隐藏楼。

## 物理、高层规则与特能双上限

默认量级规则为扉页日期 **2026.7.30** 的汪峰在吧量级参考册，使用具名配置与来源指纹。有限定档核查能量、尺度、释放形式和多次攻击条件；力、能量、功率与作用范围分开，肉身、护盾和抗性分开。高层分析区分世界观结构、角色到达、实际影响与战斗属性，按新标、道标、力标等具体口径论证，不能因“见过高层”就继承毁灭能力。

本 Skill 采用的**特能双上限**同时适用于三种口径：

1. 默认取该能力自身表现内、有依据的影响上限。
2. 最高不得超过原世界观最强角色**已经达到**的量级。

世界观结构高度不能代替最强角色已达证据，也不会把每项特能自动抬到世界最强档；施术者的肉身输出同样不直接封顶其特能。仍须分别检查目标、跨作品兼容、发动、抗性与反制；已知超限或失败不能用假设绕过。详见[双上限协议](skills/battle-scaling/references/hax-ceiling.md)。

## VS 怎么呈现

默认采用 `overview`：给宏观胜负倾向、关键胜路、条件和有依据的粗粒度胜率估计或区间。无法合理量化时说明优势程度与未决条件，不硬填数字。

用户明确要求“详细战况／具体怎么打”时使用 `process`。默认正文顺序是：

1. 双方配置、开局条件与关键假设。
2. **总体优势方获胜的一局完整战斗**：行动 → 发动／命中 → 防御／反制 → 伤势与状态 → 后续行动，直至满足胜利条件。
3. **整体胜率或优势程度及理由**，与刚才的一局示例分开。
4. **另一方的获胜机会和翻盘条件**，随后附来源与关键假设。

先独立分析优势方，再选择合理胜路写战况；对手须正常反击。无法区分优势方时不强选赢家，只能给明确标注的条件示例。过程工具结算宿主提供的行动和机制判断，不自动预测招式或模拟真实物理战斗；单局故事和分支数量都不能反推总体胜率，也不能回填成原作战绩。详见[过程协议](skills/battle-scaling/references/combat-process.md)。

## 安装与使用

克隆或下载本仓库，将 `skills/battle-scaling` **整个文件夹**安装到 Agent 技能目录。Codex 的典型位置为 `~/.codex/skills/battle-scaling`；其他支持 `SKILL.md` 的 Agent 按各自规则安装。已有同名技能时，先比较或备份，保留本机运行数据。

支持通过 GitHub 路径安装技能的工具可使用：

```text
https://github.com/LEE-path/battle-scaling/tree/main/skills/battle-scaling
```

需要 **Python 3.11+**。核心工具与小说管线使用标准库；宿主自行提供实际可用的搜索和视觉能力。视频按需使用 ffmpeg/ffprobe，图像、OCR、PDF 与科学计算任务可能需要 Pillow、PyMuPDF 或其他可选工具，不要求安装所研究外部项目的整套模型。

向宿主 Agent 提出任务即可，例如“评定某角色某版本的常态九维，并给出处与反证”或“比较双方结尾状态，先给详细战况，再解释整体胜率和翻盘条件”。Agent 按 [SKILL.md](skills/battle-scaling/SKILL.md)搜证、编制 CASE、执行审查并输出报告；CLI 本身不是独立问答模型。

分析输出包含 `report.md`、完整 `analysis.json`、CASE 副本、来源、推导、特能检查与运行清单，便于从结论追到证据和计算。

## 快速验证

以下命令从仓库根目录运行：

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py doctor
python -X utf8 tools/verify_package.py
python -X utf8 skills/battle-scaling/scripts/battle.py physics --input skills/battle-scaling/assets/cases/physics-earth-binding.json
```

使用新的输出目录，分别运行合成夹具的宏观与过程呈现：

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py analyze --input skills/battle-scaling/assets/cases/pk-dual-presentation-synthetic.json --mode all --pk overview --output runs/demo-overview
python -X utf8 skills/battle-scaling/scripts/battle.py analyze --input skills/battle-scaling/assets/cases/pk-dual-presentation-synthetic.json --mode all --pk process --output runs/demo-process
```

`--mode` 选择取证口径，`--pk` 选择呈现方式，两者独立。合成夹具用于检查工具行为，不是新的真实角色评级。

## 小说：先建档，再评级与对战

小说默认评结尾状态：完结本取最终时间跳跃后的状态，连载取已核最新章节；用户指定时期时按指定。尚未完成完整评级或没有合格档案的角色，优先建立末期能力与表现档案，再定级、VS。已有档案先核版本、覆盖、回执与宿主验收，可复用并补更新；零散查章不替代首次完整拆书。

工作链为：**核原文与版本 → 快照／分章 → 从结尾倒序实际阅读 → JSON 阅读回执 → 主 Agent 顺序接受 → 聚合与校验 → 宿主能力、实绩和状态继承验收 → 评级／VS**。逐能力检查取得、升级、保留或丧失、成功与失败、限制、抗性和原作组合；假想组合另列前提。

下面演示独立拆书库入口。将原件、书名、版本与回执路径换成实际值，`prepare` 输出须为新目录或空目录：

```powershell
python -X utf8 tools/combat-novel-refpack/refpack.py prepare --source book.txt --output runs/book-bundle --work "作品名" --edition "明确版本"
python -X utf8 tools/combat-novel-refpack/refpack.py tasks --bundle runs/book-bundle
python -X utf8 tools/combat-novel-refpack/refpack.py search --bundle runs/book-bundle --query "能力原词"
# Agent 实际阅读任务并写好回执后，逐份接受；不要并发 accept。
python -X utf8 tools/combat-novel-refpack/refpack.py accept --bundle runs/book-bundle --input runs/reviews/actual-review.json
python -X utf8 tools/combat-novel-refpack/refpack.py build --bundle runs/book-bundle
python -X utf8 tools/combat-novel-refpack/refpack.py verify --bundle runs/book-bundle
```

Skill 内置的 `skills/battle-scaling/scripts/novel_refpack.py` 也提供这六个命令，单独安装 Skill 即可使用。非 UTF-8 文本应明确提供已核编码，例如 `prepare --encoding gb18030`。

当前 Agent 默认负责阅读，不要求用户手填回执。库不内置 LLM 或付费 API 客户端；`tasks` 不会自动读书，`complete` 也只说明回执声明的覆盖完整，程序仍标记 `semantic_read_verified:false`。未读范围保留为 `partial`；全文受阻只能给部分档案与暂定结论。`CASE.candidate.json` 仍须经过表现、物理、特能与量级审查。详见[独立拆书库](tools/combat-novel-refpack/README.md)和[完整小说管线](skills/battle-scaling/references/novel-refpack-pipeline.md)。

## 目录与公开资料边界

```text
skills/battle-scaling/           Skill、规则、工具、模板与测试
tools/combat-novel-refpack/      可独立运行的论战拆书库
tools/import_handbook_corpus.py  从明确本地目录导入可选量级册 OCR
tools/verify_package.py          检查公开 Skill 静态文件指纹
docs/public-distribution.md      公开资料范围与可选依赖
NOTICE.md                       来源与许可边界
```

公开包保留代码、规则表、必要来源指纹、模板、合成／条件案例、测试及许可通知。**不附原小说全文、量级册 PDF／完整 OCR、原作截图、模型权重、私有站点运行库、密钥或个人工具路径配置。**文档中的历史来源记录不构成本机路径依赖。

默认有限与高层规则计算可运行；量级册全文检索、逐页读取及原图回看需另行提供匹配来源指纹的本地资料。导入器不下载资料或放宽哈希校验；不能把缺失资料说成已经读过。详见[公开版说明](docs/public-distribution.md)。

## 测试与许可

```powershell
python -X utf8 -m unittest discover -s skills/battle-scaling/tests -v
python -X utf8 -m unittest discover -s tools/combat-novel-refpack/tests -v
```

测试覆盖具体输入的计算、证据定位、约束、状态结算与归档。它们不保证新作品取证完整、视觉测量准确或胜率经过统计校准；需要可选本地资料而跳过的测试不算功能通过。

外部研究的吸收与取舍见[吸收边界](skills/battle-scaling/references/external-ideas.md)，上游模型不进入运行链。仓库尚未统一指定覆盖全部原创内容的开源许可证；既有第三方许可分别适用，原 `novel-refpack` 的 MIT 通知保留，软件许可不覆盖所处理作品的著作权。详见 [NOTICE](NOTICE.md)。

[简体中文](README.md) | [English](README.en.md)

![BATTLE SCALING：角色评级、VS推演、战斗写作](docs/assets/hero-zh.png)

# Battle Scaling

**给 Agent 使用的原作取证、综合量级评定、VS 推演与战斗写作 Skill · v1.12.3**

把“角色有多强、根据什么、如何获胜”整理成可追溯的证据和推导。默认采用汪吧标准，也可切换到完整 VSB 规则。宿主 Agent 负责搜索、阅读与判断；配套 Python 工具负责定位、计算、约束检查和归档。

[安装](#安装) · [任务示例](#任务示例) · [许可与鸣谢](#许可与鸣谢) · [Release](https://github.com/LEE-path/battle-scaling/releases/latest)

## 能做什么

| 能力 | 具体内容 |
|---|---|
| 原作搜证 | 逐项查能力及其实际表现，主动沿最强、同级和上下位比较查参照对象；关联官方补充作品、设定与主创原始访谈，核原文和上下文。 |
| 综合定档 | 同一版本、时期、状态与装备给一个综合主档，附九维、出处、叠法和限制；不让容易量化的局部下限代替综合判断。 |
| 物理推算 | 按需核比例尺、材料、结构、受力、毁坏机制、能量与误差；保存参数、公式、单位和可复算结果。 |
| 关系与高层结构 | 审查跨角色和跨状态的有效传递、无限层级、数学结构与叙事关系，使用所选口径的具名档位。 |
| 对战推演 | 宏观胜负、优势与翻转条件；按需写优势方获胜的一局完整战况，区分单局示例与总体胜率。 |
| 战斗写作 | 先独立评级，再按原作能力、人设、语言和世界观设计真实交锋、清楚的胜负手与结局；支持作者指定过程与胜者。 |
| 小说拆书 | 自包含的快照、分章任务、原文定位、逐能力表现、状态继承、顺序验收和末期档案；首次缺完整档案时优先拆书。 |

九维固定包含：**输出、体防、智力、战斗智商、经验、特殊技能、破坏、速度、体量**。速度等可继续分项；智力、经验使用适合该属性的能力等级，不硬套爆炸能量档。

## 两种标准，一个综合主档

- **汪吧 `wangba`（默认）**：使用随包的具名有限与高层规则，以及本 Skill 采用的特能双上限；规则及其原件指纹可追溯。
- **VSB `vsb`**：采用 VS Battles Wiki 的档位、属性、叠链、特能与对战规则；不是只替换档名，也不将汪吧特能封顶硬套过去。

每个配置只给一个综合评级。高光、通常和低谷表现用于审查代表性、出力及交手条件；**不再分别生成“最高／常态／扒下限”三套角色量级**。旧参数仅作兼容，不代表当前推荐用法。

可靠设定与比较关系可以支持上推；“表现优先”用于处理真正冲突。原作事实、合法推导、有据估档和未决条件分别标明。已知重要候选未处理完时，不以九维齐全或程序通过冒充完整评级。

## 三种对战输出

1. **宏观 VS**：配置、胜路、反制、优势程度／有据粗粒度胜率，以及对方可能获胜的条件。
2. **具体过程**：先确定总体优势方，再展开其获胜的一局，逐步处理行动、命中、防御、伤势和状态，最后说明总体胜负判断。
3. **故事版**：先执行完整独立评级，正文只写故事；没有给前因时按人物处境与能力设计入场和冲突，必须实际 PK，明确战果。对白、人物反应和关键因果充分展开，篇幅服从内容。

故事版默认取消强制新读图、视频下载和逐帧测量，复用合格档案、原作文字及可靠资料；独立评级、九维和关键能力交互不减。普通评级与论战的原有视觉取证流程保留。视频生成仅在明确请求时作为可选输出。

## 安装

需要 **Python 3.11+**，以及能搜索、阅读文件并执行工具的宿主 Agent。核心计算与拆书管线使用标准库；视觉、PDF、OCR、贴吧和视频工具按需配置，不内置模型权重。

```powershell
git clone https://github.com/LEE-path/battle-scaling.git
```

将 `skills/battle-scaling` **整个目录**安装到 Agent 的技能目录，例如 Codex 的 `~/.codex/skills/battle-scaling`。已有安装时先比较／备份，保留自己的运行数据库和资料；其他支持 `SKILL.md` 的 Agent 按其规则安装。

也可用支持 GitHub 路径的 Skill 安装器：

```text
https://github.com/LEE-path/battle-scaling/tree/main/skills/battle-scaling
```

[可选依赖与许可](THIRD_PARTY_NOTICES.md#2-按需运行的工具--optional-runtime-tools)中分别列明 PDF、OCR、视频及贴吧工具。PyMuPDF 有 AGPL／商业许可要求，不能以本仓库 MIT 替代。默认量级计算不依赖完整量级册 PDF 或 OCR；正文搜索／原图核查需要使用者自行提供有权使用的匹配原件，见[公开分发说明](docs/public-distribution.md)。

## 任务示例

```text
评定某角色指定版本的综合量级，给九维、原始来源和完整叠法。
切换到 VSB 标准，评定同一角色；说明关键属性与特能限制。
A vs B：先完成双方独立评级，给宏观胜负、关键胜路与翻转条件。
A vs B，具体过程：先写总体优势方获胜的一局，再说明整体胜率。
A vs B，故事版：保留人设与能力，补合理前因，写完整交锋和明确结局。
为某小说角色建立结尾状态档案；没有完整档案时先用拆书管线。
分析这次单次表现，核材料、受力、状态和能力机制，再定档。
```

Agent 从 [SKILL.md](skills/battle-scaling/SKILL.md)路由到所需资料。脚本不包含独立聊天模型，不会因生成索引、哈希或 JSON 就自动读懂原作。

## 本地验证与小说工具

在仓库根目录运行：

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py doctor
python -X utf8 tools/verify_package.py
python -X utf8 skills/battle-scaling/scripts/battle.py physics --input skills/battle-scaling/assets/cases/physics-earth-binding.json
```

拆书库既随 Skill 内置，也提供独立入口：

```powershell
python -X utf8 tools/combat-novel-refpack/refpack.py prepare --source book.txt --output runs/book --work "作品名" --edition "明确版本"
python -X utf8 tools/combat-novel-refpack/refpack.py tasks --bundle runs/book
# 宿主实际阅读并保存回执后，逐份顺序 accept。
python -X utf8 tools/combat-novel-refpack/refpack.py accept --bundle runs/book --input runs/actual-review.json
python -X utf8 tools/combat-novel-refpack/refpack.py build --bundle runs/book
python -X utf8 tools/combat-novel-refpack/refpack.py verify --bundle runs/book
```

未读原文保持部分覆盖，程序 `complete` 不替代宿主语义验收；候选 CASE 仍需正式定档。详见[独立拆书库](tools/combat-novel-refpack/README.md)与[完整拆书协议](skills/battle-scaling/references/novel-refpack-pipeline.md)。

## 许可与鸣谢

**原创代码及原创文档：MIT。第三方资料保留各自许可。** VSB 改编资料为 CC BY-SA 3.0；Cited Feats 普通数据为 CC BY 4.0、SCP 数据为 CC BY-SA 3.0。完整依赖、来源、许可和适用范围见 [第三方说明](THIRD_PARTY_NOTICES.md)、[NOTICE](NOTICE.md)及[当前发布包审计](docs/CURRENT-RELEASE-AUDIT.md)。

特别感谢 [novel-refpack](https://github.com/scp3500/novel-refpack) 的拆书工作流参考。流程与研究还参考了 [AutoSkill](https://github.com/ECNU-ICALK/AutoSkill)、[OmniBattle](https://github.com/Zerhal/omnibattle-ai)、[vskill](https://github.com/GentleClash/vskill)、[Fictional Ranking](https://github.com/BenCantCode/fictional-ranking)、[Animal Battle Stats](https://github.com/RamiNoodle733/animal-battle-stats)、[QuantiPhy](https://github.com/Paulineli/QuantiPhy) 和 [MangaLMM](https://github.com/manga109/MangaLMM)。[Cited Feats](https://citedfeats.com/data/) 与 [ManGo](https://arxiv.org/abs/2608.29865) 使用其已核官网／论文入口；没有虚构实现仓库。

这些研究项目不是默认运行依赖，也不表示其模型已被本包安装或复现。公开包不分发原作截图、整本小说、完整参考册 OCR、第三方模型权重或私有运行记录；写作参考使用[可复用写作经验](skills/battle-scaling/references/writing-experience.md)，不附教学故事或故事原文摘录。本次只审计当前发布包，不追溯 Git 历史，也不作无侵权或任意评级必然正确的保证。
